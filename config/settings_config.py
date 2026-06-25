from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # database_config
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str = ""  # Gán giá trị mặc định là chuỗi rỗng nếu .env để trống
    DB_NAME: str
    
    # redis_config
    REDIS_HOST: str = "redis"  # Mặc định là tên service trong docker
    REDIS_PORT: int = 6379

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str 
    ADMIN_REGISTRATION_KEY: str
    COOKIE_SECURE:str
    
    # Tất cả Expire time tính theo giây
    ACCESS_TOKEN_EXPIRE_TIME: int
    REFRESH_TOKEN_EXPIRE_TIME: int
    ONLINE_STATUS_EXPIRE_TIME: int
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
settings = Settings()