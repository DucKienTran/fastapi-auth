import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status

from config.settings_config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_TIME = settings.ACCESS_TOKEN_EXPIRE_TIME
REFRESH_TOKEN_EXPIRE_TIME = settings.REFRESH_TOKEN_EXPIRE_TIME

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_TIME)
    to_encode.update({"exp": expire, "aud": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_TIME)
    to_encode.update({"exp": expire, "aud": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str, expected_audience: str, raise_on_error: bool = True) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, audience=expected_audience, algorithms=[ALGORITHM])
        return payload
    except (jwt.InvalidAudienceError, jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        # Nếu yêu cầu ném lỗi 
        if raise_on_error:
            if isinstance(e, jwt.InvalidAudienceError):
                detail = f"Mục đích sử dụng token không hợp lệ. Yêu cầu: {expected_audience} token"
            elif isinstance(e, jwt.ExpiredSignatureError):
                detail = "Token đã hết hạn sử dụng"
            else:
                detail = "Token không hợp lệ"
            
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
        
        # Nếu không yêu cầu ném lỗi (Dùng cho logout, delete-account)
        return None
    