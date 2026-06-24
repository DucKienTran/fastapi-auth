import re
from typing import Optional, Self # Thư viện Regular Expression để kiểm tra chuỗi ký tự

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# REGISTER SCHEMA
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Mật khẩu phải có ít nhất 8 ký tự.")

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Mật khẩu phải chứa ít nhất 1 chữ cái viết hoa.")
        
        if not re.search(r"[a-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Mật khẩu phải chứa cả ký tự chữ thường và chữ số.")
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")
            
        return value

# CHANGE PASSWORD SCHEMA
class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, description="Mật khẩu mới phải có ít nhất 8 ký tự.")
    confirm_new_password: str = Field(..., min_length=8, description="Mật khẩu mới phải có ít nhất 8 ký tự.")

    @model_validator(mode='after')
    def check_passwords_match(self) -> Self:
        if self.new_password != self.confirm_new_password:
            raise ValueError("Mật khẩu nhập lại không trùng nhau.")
        return self
    
    @field_validator("new_password")
    @classmethod
    def validate_strong_new_password(cls, value: str) -> str:
        if not re.search(r"[A-Z]", value):
            raise ValueError("Mật khẩu mới phải chứa ít nhất 1 chữ cái viết hoa.")
        
        if not re.search(r"[a-z]", value) or not re.search(r"[0-9]", value):
            raise ValueError("Mật khẩu mới phải chứa cả ký tự chữ thường và chữ số.")
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Mật khẩu mới phải chứa ít nhất 1 ký tự đặc biệt (!@#$%^&*...).")
            
        return value

# CHECK STATUS SCHEMA
class UserStatus(BaseModel):
    user_id: int
    email: str
    role: str
    status: str    
    message: str
    last_active: Optional[int] = None
    
# LOGIN SCHEMA
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# RESPONSE SCHEMA
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str 

    class Config:
        from_attributes = True