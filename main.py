import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from routers.users_routers import router as users_router
from routers.auth_routers import router as auth_router
from config.database_config import engine, Base
from config.logging_config import setup_logging
from config.redis_config import redis_client

Base.metadata.create_all(bind=engine)

setup_logging()
logger = logging.getLogger(__name__)

# Khởi tạo MySQL Database 
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Kết nối MySQL Database thành công.")
except Exception as e:
    logger.critical(f"LỖI KẾT NỐI DATABASE: ỨNG DỤNG KHÔNG THỂ KHỞI CHẠY: {str(e)}")
    raise e

# Khởi tạo Redis Database
try:
    redis_client.ping()
    logger.info("Kết nối Redis thành công.")
except Exception as e:
    logger.critical(f"LỖI KẾT NỐI REDIS: ỨNG DỤNG KHÔNG THỂ KHỞI CHẠY: {str(e)}")
    raise e

# Khởi tạo FastAPI
app = FastAPI(
    title="Auth API Demo", 
    description="Mini project about basic FastAPI",
)

# Global Exception Handler - Hứng tất cả lỗi chưa được catch ở router, tránh crash server và ghi log chi tiết
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"CRASH HỆ THỐNG: Lỗi bất ngờ xuất hiện tại Endpoint {request.method} {request.url.path}")
    logger.error(traceback.format_exc()) 
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Đã xảy ra lỗi nội bộ trên Server. Vui lòng liên hệ Admin hoặc thử lại sau."
        }
    )

# Endpoint /ping Kiểm tra server hoạt động
@app.get("/ping", tags=["Health Check"])
def ping_server():
    return {"message": "pong"}

app.include_router(users_router)    
app.include_router(auth_router)