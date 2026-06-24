from fastapi import APIRouter, Cookie, HTTPException, status, Response, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config.database_config import get_db
from config.redis_config import redis_client
from config.settings_config import settings
from models.user_model import UserModel

import logging
import time

from schemas.user_schema import UserRegister, UserResponse, UserLogin
from schemas.token_schema import TokenResponse

from utils.password_hash import hash_password, verify_password
from utils.jwt_handler import (
    create_access_token, 
    create_refresh_token, 
    decode_token, 
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)

REFRESH_TOKEN_EXPIRE_TIME = settings.REFRESH_TOKEN_EXPIRE_TIME
ONLINE_STATUS_EXPIRE_TIME = settings.ONLINE_STATUS_EXPIRE_TIME

# Hàm chặn người dùng đã đăng nhập không được đăng ký hay lại đăng nhập
security_optional = HTTPBearer(auto_error = False)
def disallow_authenticated(credentials: HTTPAuthorizationCredentials = Depends(security_optional)):
    if credentials:
        token = credentials.credentials

        payload = decode_token(token, expected_audience="access", raise_on_error=False)
        if payload:
            logger.warning(f"Truy cập bị chặn: người dùng [{payload.get("id")}, {payload.get("sub")}, {payload.get("role")}] cố tình truy cập API ẩn danh")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bạn đã đăng nhập hệ thống. Vui lòng đăng xuất trước khi thực hiện hành động này."
            )
        
# Endpoint đăng ký tài khoản Client
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(disallow_authenticated)])
def register_client(user_data: UserRegister, db: Session = Depends(get_db)):

    # Quét email trùng lặp 
    existing_user = db.query(UserModel).filter(UserModel.email == user_data.email).first()
    if existing_user:
        logger.warning(f"Đăng ký client thất bại: Email {user_data.email} đã tồn tại")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký trên hệ thống."
        )
    
    hashed_pass = hash_password(user_data.password)
    
    new_user = UserModel(
        email=user_data.email,
        password=hashed_pass,  
        role="client"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Đăng ký Client thành công: [{new_user.id}, {user_data.email}, {new_user.role}]")
    return new_user

# Endpoint đăng ký tài khoản Admin (Yêu cầu admin_key)
@router.post("/register-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(disallow_authenticated)])
def register_admin(user_data: UserRegister, admin_key: str, db: Session = Depends(get_db)):

    # Xác thực admin_key
    if admin_key != settings.ADMIN_REGISTRATION_KEY:
        logger.warning(f"Đăng ký admin thất bại: Mã xác thực Admin không hợp lệ")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mã xác thực Admin không hợp lệ."
        )
    
    # Quét email trùng lặp 
    existing_user = db.query(UserModel).filter(UserModel.email == user_data.email).first()
    if existing_user:
        logger.warning(f"Đăng ký admin thất bại: Email {user_data.email} đã tồn tại")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được đăng ký trên hệ thống."
        )
    
    hashed_pass = hash_password(user_data.password)
    
    new_user = UserModel(
        email=user_data.email,
        password=hashed_pass,  
        role="admin"
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"Đăng ký Admin thành công: [{new_user.id}, {user_data.email}, {new_user.role}]")
    return new_user

# Endpoint đăng nhập, trả về Access Token, lưu Refresh Token trong Cookie HttpOnly, 
# lưu trạng thái online và thời gian hoạt động cuối cùng trên Redis
@router.post("/login", response_model=TokenResponse, dependencies=[Depends(disallow_authenticated)])
def login_user(response: Response, 
               form_data: UserLogin, 
               db: Session = Depends(get_db)):  
    
    target_user = db.query(UserModel).filter(UserModel.email == form_data.email).first()
            
    if not target_user:
        logger.warning(f"Đăng nhập thất bại: Email {form_data.email} không tồn tại")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email hoặc mật khẩu không chính xác."
        )
    
    if not verify_password(form_data.password, target_user.password):
        logger.warning(f"Đăng nhập thất bại: Email {form_data.email} sai mật khẩu")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email hoặc mật khẩu không chính xác."
        )
    
    token_payload = {"id": target_user.id, 
                     "sub": target_user.email, 
                     "role": target_user.role}
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    # Lưu Refresh Token trong Cookie HttpOnly
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_TIME
    )

    # Lưu trạng thái online
    redis_client.setex(f"user:status:{target_user.id}", ONLINE_STATUS_EXPIRE_TIME, "online")
    # Lưu thời gian hoạt động cuối cùng 
    redis_client.setex(f"user:last_active:{target_user.id}", REFRESH_TOKEN_EXPIRE_TIME, int(time.time()))

    logger.info(f"Đăng nhập với tư cách {target_user.role} thành công: [{target_user.id}, {target_user.email}, {target_user.role}]")
    return {

        "access_token": access_token,
        "token_type": "bearer"  
    }


# Endpoint cấp lại Access Token mới bằng Refresh Token
@router.post("/token/refresh", response_model=TokenResponse)
def refresh_token(response: Response, 
                  refresh_token: str = Cookie(None),
                  db: Session = Depends(get_db)):
    
    # Kiểm tra Client có gửi Refresh Token trong Cookie không
    if not refresh_token:
        logger.warning(f"Không có Refresh Token trong Cookie")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã hết hạn hoặc không hợp lệ (Missing Cookie)."
        )
    
    # Kiểm tra trên Redis xem Refresh Token này có hơp lệ không
    is_blacklisted = redis_client.get(f"blacklist:refresh:{refresh_token}")
    if is_blacklisted:
        logger.warning(f"Phát hiện hành vi tái sử dụng Refresh Token: {refresh_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Phiên làm việc của bạn đã hết hạn hoặc thay đổi. Vui lòng đăng nhập lại."
        )
    

    payload = decode_token(refresh_token, expected_audience="refresh")
    user_id = payload.get("id")
    user_email = payload.get("sub")
    user_role = payload.get("role")

    # Kiểm tra tài khoản có bị admin xóa không 
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        logger.warning("Tài khoản không tồn tại hoặc đã bị xóa.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị xóa."
        )
    
    # Đưa Refresh Token cũ vào blacklist trên Redis ngay sau khi dùng xong
    refresh_ttl = int(payload.get("exp") - time.time())
    if refresh_ttl > 0:
        redis_client.setex(f"blacklist:refresh:{refresh_token}", refresh_ttl, "true")
    
    new_payload = { 
        "id": user_id,
        "sub": user_email, 
        "role": user_role
    }

    # Lưu Refresh Token mới vào Cookie HttpOnly 
    response.set_cookie(
        key="refresh_token",
        value=create_refresh_token(new_payload),
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_TIME
    )

    logger.info(f"Cấp lại token thành công cho người dùng: [{user_id}, {user_email}, {user_role}]")

    return {
        "access_token": create_access_token(new_payload),
        "token_type": "bearer"
    }

# Endpoint đăng xuất, vô hiệu hóa Refresh Token
@router.post("/logout", status_code=status.HTTP_200_OK)
def logout_user(response : Response, refresh_token: str = Cookie(None)): 

    # Thêm Refresh Token vào blacklist để ngăn tái sử dụng
    if refresh_token:
        payload_refresh = decode_token(refresh_token, expected_audience="refresh", raise_on_error=False)

        if payload_refresh:
            refresh_ttl = int(payload_refresh.get("exp") - time.time())
            if (refresh_ttl > 0):
                redis_client.setex(f"blacklist:refresh:{refresh_token}", refresh_ttl, "true")

            user_id = payload_refresh.get("id")
            user_email = payload_refresh.get("sub")
            user_role = payload_refresh.get("role")

            # Lưu lại lần online cuối trước khi bấm logout
            redis_client.setex(f"user:last_active:{user_id}", REFRESH_TOKEN_EXPIRE_TIME, int(time.time()))
            # Xóa trạng thái online
            redis_client.delete(f"user:status:{user_id}")

            logger.info(f"Người dùng đăng xuất thành công. Tài khoản [{user_id}, {user_email}, {user_role}] đã bị vô hiệu hóa Refresh Token.")
        else:
            logger.warning("Phát hiện request logout kèm theo Refresh Token lỗi cấu trúc.")

    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")
    return {"detail": "Đăng xuất thành công."}