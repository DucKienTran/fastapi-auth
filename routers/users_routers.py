import time

from fastapi import APIRouter, Cookie, HTTPException, Response, status, Depends
from sqlalchemy.orm import Session
from typing import List, Optional, Union

import logging

from config.database_config import get_db
from config.redis_config import redis_client
from config.settings_config import settings

from models.user_model import UserModel
from schemas.user_schema import UserResponse, ChangePassword, UserStatus

from utils.jwt_handler import create_access_token, create_refresh_token, decode_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from utils.password_hash import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()

logger = logging.getLogger(__name__)

REFRESH_TOKEN_EXPIRE_TIME = settings.REFRESH_TOKEN_EXPIRE_TIME
ONLINE_STATUS_EXPIRE_TIME = settings.ONLINE_STATUS_EXPIRE_TIME

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials

    payload = decode_token(token, expected_audience="access")
    
    # Kiểm tra người dùng có bị admin xóa không
    email = payload.get("sub")
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user:
        logger.warning(f"Xác thực thất bại: Token hợp lệ nhưng không tìm thấy Email '{email}' trong Database.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Người dùng không tồn tại"
        )
    

    # Cập nhật trạng thái online
    redis_client.setex(f"user:status:{user.id}", ONLINE_STATUS_EXPIRE_TIME, "online")
    # Cập nhật thời gian hoạt động cuối cùng 
    redis_client.setex(f"user:last_active:{user.id}", REFRESH_TOKEN_EXPIRE_TIME, int(time.time()))

    return user

@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserModel = Depends(get_current_user)):
    logger.info(f"Truy cập thông tin cá nhân thành công: {current_user.id}, {current_user.email}, {current_user.role}")
    return current_user

@router.get("/all", response_model=List[UserResponse])
def get_all_users(current_user: UserModel = Depends(get_current_user), 
                  db: Session = Depends(get_db)):
    if current_user.role != "admin":
        logger.warning(
            f"Truy cập trái phép: Người dùng [{current_user.id}, {current_user.email}, {current_user.role}] "
            f"cố gắng truy cập API lấy toàn bộ danh sách users")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập vào danh sách người dùng (Yêu cầu quyền Admin)."
        )
    
    logger.info(f"Truy cập danh sách người dùng thành công: ADMIN [{current_user.id}, {current_user.email}, {current_user.role}]")
    users = db.query(UserModel).all()
    return users

def _format_user_status(target_user: UserModel) -> dict:
    """Hàm helper để tính toán trạng thái và thời gian offline của một user"""
    user_id = target_user.id
    user_email = target_user.email 
    user_role = target_user.role
    
    status_val = redis_client.get(f"user:status:{user_id}")
    last_active_raw = redis_client.get(f"user:last_active:{user_id}")
    last_active_int = int(last_active_raw) if last_active_raw else None

    # Online
    if status_val:
        return {
            "user_id": user_id, 
            "email": user_email, 
            "role": user_role,
            "status": "online", 
            "message": "Đang hoạt động",
            "last_active": last_active_int
        }

    # Offline quá 7 ngày hoặc chưa từng Online
    if not last_active_int:
        return {
            "user_id": user_id, 
            "email": user_email, 
            "role": user_role,
            "status": "offline", 
            "message": "Không hoạt động",
            "last_active": None
        }
    
    # Offline trong 7 ngày
    seconds_offline = int(time.time()) - last_active_int
    ONE_MINUTE, ONE_HOUR, ONE_DAY = 60, 3600, 86400

    if seconds_offline < ONE_HOUR:
        message = f"Hoạt động {seconds_offline // ONE_MINUTE} phút trước" 
    elif seconds_offline < ONE_DAY:
        message = f"Hoạt động {seconds_offline // ONE_HOUR} giờ trước"
    else:
        message = f"Hoạt động {seconds_offline // ONE_DAY} ngày trước"
    
    return {
        "user_id": user_id, 
        "email": user_email, 
        "role": user_role,
        "status": "offline", 
        "message": message,
        "last_active": last_active_int
    }

@router.get("/get-status", status_code=status.HTTP_200_OK, response_model=Union[UserStatus, List[UserStatus]]) 
def get_user_status(target_id: Optional[int] = None,
                    current_user: UserModel = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    
    if current_user.role != "admin":
        logger.warning(f"Cảnh báo bảo mật: User [{current_user.id}] cố gắng truy cập tính năng xem trạng thái.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Bạn không có quyền xem trạng thái của người dùng (Yêu cầu quyền Admin)."
        )
    
    if target_id:
        target_user = db.query(UserModel).filter(UserModel.id == target_id).first()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy người dùng này.")
        
        return _format_user_status(target_user)
    
    all_users = db.query(UserModel).all()
    all_statuses = [_format_user_status(u) for u in all_users]
    
    return all_statuses
    
# Endpoint thay đổi mật khẩu, sau khi thay đổi sẽ cấp luôn access và refresh token mới
@router.put("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    data: ChangePassword, 
    response: Response,
    current_user: UserModel = Depends(get_current_user), 
    refresh_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    # Kiểm tra mật khẩu cũ nhập vào có khớp với database không
    if not verify_password(data.old_password, current_user.password):
        logger.warning(f"Đổi mật khẩu thất bại: Tài khoản [{current_user.id}] nhập sai mật khẩu cũ.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu cũ không chính xác."
        )
    
    # Kiểm tra mật khẩu mới có trùng với mật khẩu cũ không
    if verify_password(data.new_password, current_user.password):
        logger.warning(f"Đổi mật khẩu thất bại: Tài khoản [{current_user.id}] nhập mật khẩu mới trùng với mật khẩu cũ.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới không được trùng với mật khẩu cũ."
        )
    
    # Kiểm tra Client có gửi Refresh Token trong Cookie không
    if not refresh_token:
        logger.warning(f"Không có Refresh Token trong Cookie")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập đã hết hạn hoặc không hợp lệ (Missing Cookie)."
        )
    
    # Đưa Refresh Token cũ vào blacklist trên Redis ngay sau khi đổi mật khẩu
    is_blacklisted = redis_client.get(f"blacklist:refresh:{refresh_token}")
    if is_blacklisted:
        logger.warning(f"Phát hiện hành vi tái sử dụng Refresh Token: {refresh_token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Phiên làm việc của bạn đã hết hạn hoặc thay đổi. Vui lòng đăng nhập lại."
        )
    
    payload = decode_token(refresh_token, expected_audience="refresh")
    if payload.get("id") != current_user.id:
        logger.error(f"CẢNH BÁO: Phát hiện bất đồng bộ định danh! "
                     f"Access Token ID [{current_user.id}] gửi kèm Refresh Token ID [{payload.get('id')}].")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thông tin xác thực không đồng nhất."
        )
    
    user_id = current_user.id
    user_email = current_user.email
    user_role = current_user.role

    # Băm mật khẩu mới và cập nhật vào MySQL
    current_user.password = hash_password(data.new_password)
    db.commit()
    
    logger.info(f"Đổi mật khẩu thành công cho tài khoản: [{user_id}, {user_email}, {user_role}]")

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

    logger.info(f"Cấp lại token thành công cho người dùng [{user_id}, {user_email}, {user_role}] sau khi đổi mật khẩu")
    
    return {"access_token": create_access_token(new_payload),
        "token_type": "bearer",
        "detail": "Thay đổi mật khẩu thành công."}

@router.delete("/delete-account", status_code=status.HTTP_200_OK)
def delete_account(
    response: Response,
    target_id: Optional[int] = None,  
    refresh_token: str = Cookie(None),  
    current_user: UserModel = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Nếu target_id trống hoặc bằng chính id người gọi thì là tự xóa
    is_self_deletion = (target_id is None) or (target_id == current_user.id)
    
    if is_self_deletion:
        user_to_delete = current_user
    else:
        # Nếu muốn xóa người khác, yêu cầu phải có quyền Admin
        if current_user.role != "admin":
            logger.warning(f"Cảnh báo: Người dùng [{current_user.id}] cố gắng xóa tài khoản [{target_id}] mà không có quyền.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Bạn không có quyền xóa tài khoản của người khác."
            )
        
        # Tìm user cần xóa trong Database
        user_to_delete = db.query(UserModel).filter(UserModel.id == target_id).first()
        logger.warning("Không tìm thấy tài khoản cần xóa trong database")
        if not user_to_delete:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản cần xóa.")
        
        # Ngăn chặn Admin xóa một Admin khác 
        # if user_to_delete.role == "admin":
        #     logger.warning(f"Cảnh báo: Admin [{current_user.id}] cố gắng xóa tài khoản Admin [{target_id}] khác")
        #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không thể xóa tài khoản của một Admin khác.")

    user_info = f"[{user_to_delete.id}, {user_to_delete.email}, {user_to_delete.role}]"

    # Xóa dữ liệu về trạng thái trên Redis của user bị xóa
    redis_client.delete(f"user:status:{user_to_delete.id}")
    redis_client.delete(f"user:last_active:{user_to_delete.id}")

    # Xóa bản ghi trong MySQL
    logger.info(f"Xóa tài khoản người dùng: {user_info} khỏi database.")
    db.delete(user_to_delete)
    db.commit()

    
    if is_self_deletion:
        # Xóa Refresh Token khỏi cookie
        logger.info(f"Xóa Refresh Token khỏi Cookie HttpOnly cho tài khoản: {user_info}")
        response.delete_cookie(key="refresh_token", httponly=True, samesite="lax")

        # Thêm Refresh token vào Blacklist trên Redis (nếu chưa expire)
        if refresh_token:
            payload_refresh = decode_token(refresh_token, expected_audience="refresh", raise_on_error=False)
            if payload_refresh:
                refresh_ttl = int(payload_refresh.get("exp", 0) - time.time())
                if refresh_ttl > 0:
                    redis_client.setex(f"blacklist:refresh:{refresh_token}", refresh_ttl, "true")

        logger.info(f"Tài khoản {user_info} đã tự xóa thành công.")
        return {"detail": "Tài khoản của bạn đã bị xóa vĩnh viễn khỏi hệ thống."}
    '''
    Known limitation:
    Hiện tại chỉ thêm được refresh token của người tự xóa vào blacklist,
    còn người bị admin xóa thì chưa thêm được refresh token vào blacklist.
    '''
    logger.info(f"Admin [{current_user.id}] đã xóa thành công tài khoản: {user_info}")
    return {"detail": f"Đã xóa tài khoản {user_info} thành công khỏi hệ thống."}