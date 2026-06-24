from sqlalchemy import Column, Integer, String
from config.database_config import Base

class UserModel(Base):
    __tablename__ = "users"

    # Định nghĩa các cột trong MySQL
    id = Column(Integer, primary_key=True, index=True, autoincrement=True) 
    email = Column(String(150), unique=True, index=True, nullable=False)  
    password = Column(String(255), nullable=False)                         
    role = Column(String(50), default="user", nullable=False)             