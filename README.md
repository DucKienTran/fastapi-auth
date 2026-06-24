# FastAPI Authentication Service

Project này xây dựng hệ thống xác thực người dùng (Authentication & Authorization) sử dụng FastAPI, JWT 2 tầng, Redis và MySQL.

---

## 1. Giới thiệu

Hệ thống cung cấp các chức năng xác thực cơ bản cho một ứng dụng web:

- Đăng ký và đăng nhập tài khoản.
- Xác thực danh tính qua JWT (Access Token + Refresh Token).
- Phân quyền người dùng theo role (`client` / `admin`).
- Theo dõi trạng thái online và thời gian hoạt động cuối của từng người dùng qua Redis.
- Quản lý tài khoản: đổi mật khẩu, xóa tài khoản.

---

## 2. Luồng hoạt động

### 2.1. Đăng ký & Đăng nhập

```
Client
  │
  ├─ POST /auth/register ──────────────────► Validate schema
  │                                               │
  │                                          Hash password (bcrypt)
  │                                               │
  │                                          Lưu vào MySQL
  │                                               │
  │◄──────────────────────────────────────── UserResponse (201)
  │
  ├─ POST /auth/login ─────────────────────► Kiểm tra email + password
  │                                               │
  │                                          Tạo Access Token 
  │                                          Tạo Refresh Token 
  │                                               │
  │                                          Lưu trạng thái online → Redis
  │                                               │
  │◄──────────────────────────── access_token (body) + refresh_token (HttpOnly Cookie)
```

### 2.2. Xác thực & Làm mới Token

```
Client
  │
  ├─ GET /users/me ────────────────────────► Đọc Authorization Header
  │   (Bearer access_token)                      │
  │                                          Decode & verify JWT (aud="access")
  │                                               │
  │                                          Tra cứu user trong MySQL
  │                                               │
  │                                          Cập nhật last_active → Redis
  │                                               │
  │◄──────────────────────────────────────── UserResponse (id, email, role)
  │
  ├─ POST /auth/token/refresh ─────────────► Đọc refresh_token từ Cookie
  │                                               │
  │                                          Kiểm tra blacklist trên Redis
  │                                               │
  │                                          Decode & verify JWT (aud="refresh")
  │                                               │
  │                                          Đưa refresh_token cũ vào blacklist
  │                                          Tạo cặp token mới (Rotation)
  │                                               │
  │◄──────────────────────────── access_token mới (body) + refresh_token mới (Cookie)
```

### 2.3. Đăng xuất

```
Client
  │
  ├─ POST /auth/logout ────────────────────► Đọc refresh_token từ Cookie
  │                                               │
  │                                          Decode token (không throw nếu lỗi)
  │                                               │
  │                                          Thêm vào Redis blacklist
  │                                          Xóa trạng thái online
  │                                          Cập nhật last_active
  │                                               │
  │                                          Xóa Cookie refresh_token
  │                                               │
  │◄──────────────────────────────────────── HTTP_status 200 OK
```

---

## 3. Các Endpoint

| Endpoint | Method | Mô tả | Yêu cầu Auth |
|---|---|---|---|
| `/ping` | GET | Kiểm tra server hoạt động | Không |
| `/auth/register` | POST | Đăng ký tài khoản `client` | Không |
| `/auth/register-admin` | POST | Đăng ký tài khoản `admin` (cần `admin_key`) | Không |
| `/auth/login` | POST | Đăng nhập, trả về token | Không |
| `/auth/token/refresh` | POST | Cấp lại access token từ refresh token trong Cookie | Không (dùng Cookie) |
| `/auth/logout` | POST | Đăng xuất, vô hiệu hóa refresh token | Không (dùng Cookie) |
| `/users/me` | GET | Lấy thông tin tài khoản hiện tại | Bearer Token |
| `/users/all` | GET | Lấy danh sách toàn bộ người dùng | Bearer Token (Admin) |
| `/users/get-status` | GET | Xem trạng thái online của người dùng | Bearer Token (Admin) |
| `/users/change-password` | PUT | Đổi mật khẩu, cấp lại token mới | Bearer Token |
| `/users/delete-account` | DELETE | Xóa tài khoản (tự xóa hoặc Admin xóa) | Bearer Token |

> Các endpoint `/auth/register`, `/auth/register-admin`, `/auth/login` sẽ từ chối request nếu người dùng đã đăng nhập (có Access Token hợp lệ trong header).

> Endpoint `/users/get-status` sẽ không ghi log để khi chạy liên tục theo chu kỳ (Polling) tránh tình trạng spam log/ log pollution.
---

## 4. Cấu trúc thư mục

```
fastapi-auth/
├── algorithms/
├── config/
│   ├── database_config.py     # Kết nối MySQL (SQLAlchemy)
│   ├── redis_config.py        # Kết nối Redis
│   └── settings_config.py     # Đọc biến môi trường từ .env
│
├── models/
│   └── user_model.py          # ORM model bảng users
│
├── routers/
│   ├── auth_routers.py        # Các route xác thực (register, login, logout, refresh)
│   └── users_routers.py       # Các route người dùng (me, all, status, change-password, delete)
│
├── schemas/
│   ├── token_schema.py        # Schema phản hồi token
│   └── user_schema.py         # Schema đăng ký, đăng nhập, đổi mật khẩu, phản hồi
│
├── utils/
│   ├── jwt_handler.py         # Tạo và giải mã JWT (access + refresh)
│   └── password_hash.py       # Hash và xác minh mật khẩu 
│
├── .env                       # Biến môi trường 
├── .env.example               # Mẫu file .env
├── .gitignore
├── main.py                    # Khởi tạo FastAPI app, đăng ký router
├── README.md
└── requirements.txt
```

---

## 5. Cài đặt môi trường

| Thành phần | Yêu cầu |
|---|---|
| Python | 3.9 trở lên |
| MySQL | 8.0 trở lên |
| Redis | 6.0 trở lên |
| pip | Trình quản lý package Python |
| Git | Để clone project |
| IDE | VS Code, PyCharm hoặc tương đương |
| Hệ điều hành | Windows, Linux hoặc macOS |

### 5.1. Clone project

```bash
git clone https://github.com/<your-username>/fastapi-auth.git
cd fastapi-auth
```

### 5.2. Tạo môi trường ảo

Trên Windows:

```bash
python -m venv .venv
```

Trên Linux hoặc macOS:

```bash
python3 -m venv .venv
```

### 5.3. Kích hoạt môi trường ảo

Trên Windows:

```bash
.venv\Scripts\activate
```

Trên Linux hoặc macOS:

```bash
source .venv/bin/activate
```

### 5.4. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

Nếu cài thêm thư viện mới trong quá trình phát triển, cập nhật lại `requirements.txt`:

```bash
pip freeze > requirements.txt
```

---

## 6. Cấu hình biến môi trường

Tạo file `.env` tại thư mục gốc dựa trên `.env.example`:

```bash
cp .env.example .env
```

Nội dung file `.env`:

```env
# Database
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/your-database-name

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# JWT
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_TIME=900          # Đơn vị: giây (= 15 phút)
REFRESH_TOKEN_EXPIRE_TIME=604800      # Đơn vị:  giây (= 7 ngày)

# Redis TTL
ONLINE_STATUS_EXPIRE_TIME=300        # Đơn vị: giây (= 5 phút)

# Admin
ADMIN_REGISTRATION_KEY=your-admin-key-here

# Cookie
COOKIE_SECURE=False                  # Đặt True khi deploy HTTPS
```

> **Lưu ý:** File `.env` sẽ không commit lên Git. File này đã được thêm vào `.gitignore`.

---

## 7. Khởi động các dịch vụ phụ thuộc

Project yêu cầu MySQL và Redis phải chạy trước khi khởi động server. Thực hiện theo thứ tự sau mỗi lần mở máy:

### 7.1. Khởi động MySQL (XAMPP)

1. Mở XAMPP Control Panel.
2. Nhấn Start tại dòng MySQL.
3. Đảm bảo cột Port hiển thị `3306`.

Lần đầu chạy:

4. Nhấn Start tại dòng Apache
5. Nhấn Admin tại dòng MySQL để truy cập phpMyAdmin
6. Tạo database với tên khớp với `DATABASE_URL` trong file `.env`.

### 7.2. Khởi động Redis (Docker)

Đảm bảo Docker Desktop đang chạy, sau đó mở terminal và chạy:

```bash
docker run -d --name redis-auth -p 6379:6379 redis
```

>Lệnh trên chỉ cần chạy lần đầu để tạo container. Từ lần sau, container đã tồn tại, chỉ cần start lại:

```bash
docker start redis-auth
```

Kiểm tra Redis đã chạy:

```bash
docker ps
```
Cột STATUS của container redis-auth phải hiển thị Up.
### 7.3. Khởi động server FastAPI
Kích hoạt môi trường ảo (nếu chưa kích hoạt), sau đó chạy:

```bash
uvicorn main:app --reload 
```

Server chạy tại: http://127.0.0.1:8000

Swagger UI (tài liệu API tương tác): http://127.0.0.1:8000/docs
## 8. Giải thích các cơ chế bảo mật

### 8.1. JWT 2 tầng (Access + Refresh Token)

| | Access Token | Refresh Token |
|---|---|---|
| Lưu ở đâu | Authorization Header | HttpOnly Cookie |
| Thời hạn | 15 phút | 7 ngày |
| Mục đích (`aud`) | `"access"` | `"refresh"` |
| Dùng để | Xác thực request | Lấy Access Token mới |

- Access Token có thời hạn ngắn để giới hạn thiệt hại nếu bị lộ.
- Refresh Token lưu trong HttpOnly Cookie, JavaScript phía client không đọc được.
- Mỗi lần dùng Refresh Token, token cũ bị đưa vào blacklist và token mới được cấp (Refresh Token Rotation).

### 8.2. Redis Blacklist

Khi Refresh Token bị vô hiệu hóa (logout, đổi mật khẩu, xóa tài khoản), token được lưu vào Redis với TTL bằng thời gian sống còn lại của token. Mọi request dùng token trong blacklist đều bị từ chối.

### 8.3. Trạng thái Online

Redis lưu hai key cho mỗi người dùng:

- `user:status:{id}` — giá trị `"online"`, TTL 5 phút, được gia hạn mỗi khi có request hợp lệ.
- `user:last_active:{id}` — Unix timestamp lần hoạt động cuối, TTL 7 ngày.

Admin có thể xem trạng thái của từng người dùng hoặc toàn bộ danh sách qua `/users/get-status`.

### 8.4. Xác thực mật khẩu

Mật khẩu yêu cầu:
- Ít nhất 8 ký tự.
- Ít nhất 1 chữ hoa, 1 chữ thường, 1 chữ số.
- Ít nhất 1 ký tự đặc biệt (`!@#$%^&*...`).

Mật khẩu được hash bằng `bcrypt` trước khi lưu vào database.

---

## 9. Phân quyền

| Chức năng | `client` | `admin` |
|---|---|---|
| Xem thông tin bản thân (`/users/me`) | ✅ | ✅ |
| Đổi mật khẩu | ✅ | ✅ |
| Tự xóa tài khoản | ✅ | ✅ |
| Xem danh sách người dùng | ❌ | ✅ |
| Xem trạng thái online | ❌ | ✅ |
| Xóa tài khoản người khác | ❌ | ✅ |

---

## 10. Known Limitations

- Khi Admin xóa tài khoản của người khác, Refresh Token của người đó **không bị blacklist ngay lập tức** vì server không lưu trữ Refresh Token theo user_id. Token sẽ tự hết hạn sau tối đa 7 ngày.  Hiện tại code đang xử lý bằng cách thêm một bước kiểm tra xem email đó còn tồn tại hay không trong get_current_user().Việc truy vấn vào database sẽ trả về lỗi 401 vì user không còn tồn tại.
