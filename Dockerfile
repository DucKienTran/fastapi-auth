# ==============================
# STAGE 1: Cài đặt & Build Dependencies
# ==============================
FROM python:3.12-slim AS builder

WORKDIR /app

# Khai báo các biến môi trường cho Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt các công cụ hệ thống cần thiết 
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmariadb-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Cài đặt dependencies vào thư mục tạm /install
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy toàn bộ mã nguồn vào app ở bản builder
COPY . .

# ==============================
# STAGE 2: Khởi chạy Production 
# ==============================
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cài đặt thư viện runtime 
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# Copy thư viện và mã nguồn từ Stage builder
COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# Mở port FastAPI
EXPOSE 8000

# Lệnh chạy ứng dụng 
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]