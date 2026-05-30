# HƯỚNG DẪN DEPLOY LÊN RENDER.COM (MIỄN PHÍ)

## MỤC LỤC
1. [Chuẩn bị](#1-chuẩn-bị)
2. [Tạo tài khoản GitHub](#2-tạo-tài-khoản-github)
3. [Upload code lên GitHub](#3-upload-code-lên-github)
4. [Deploy trên Render.com](#4-deploy-trên-rendercom)
5. [Sau khi deploy](#5-sau-khi-deploy)
6. [Cách sử dụng](#6-cách-sử-dụng)

---

## 1. CHUẨN BỊ

### Cần có:
- Tài khoản **GitHub** (miễn phí)
- Tài khoản **Render.com** (miễn phí) - đăng ký bằng GitHub

### Cấu trúc thư mục web:
```
web_hoadon/
├── app.py                 ← Code Flask chính
├── requirements.txt       ← Thư viện cần cài
├── Procfile             ← Cấu hình chạy app
├── render.yaml          ← Cấu hình deploy
├── templates/           ← Giao diện HTML
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   └── ...
```

---

## 2. TẠO TÀI KHOẢN GITHUB

### Bước 2.1: Đăng ký GitHub
1. Mở trình duyệt → vào https://github.com
2. Click **Sign up**
3. Nhập email, password, username
4. Xác nhận email

### Bước 2.2: Tạo Repository mới
1. Đăng nhập GitHub
2. Click nút **"+"** góc trên phải → **New repository**
3. Điền thông tin:
   - **Repository name:** `hoadon-manager`
   - **Description:** `Web app quản lý hóa đơn`
   - **Public/Private:** Chọn **Private** (bảo mật)
4. Click **Create repository**

---

## 3. UPLOAD CODE LÊN GITHUB

### Cách 1: Dùng Git Desktop (Dễ nhất)

#### Bước 3.1: Tải GitHub Desktop
1. Vào https://desktop.github.com
2. Tải và cài đặt

#### Bước 3.2: Clone repository
1. Mở GitHub Desktop
2. Đăng nhập tài khoản GitHub
3. Click **Clone a repository**
4. Chọn `hoadon-manager` → chọn thư mục lưu (VD: `Desktop\hoadon-manager`)

#### Bước 3.3: Copy code vào
1. Mở thư mục đã clone
2. Copy tất cả file từ `web_hoadon/` vào đó
3. Cấu trúc thư mục sau khi copy:
   ```
   hoadon-manager/
   ├── app.py
   ├── requirements.txt
   ├── Procfile
   ├── render.yaml
   └── templates/
   ```

#### Bước 3.4: Commit và Push
1. Trong GitHub Desktop, sẽ thấy các file mới
2. Nhập **Summary:** `Initial commit`
3. Click **Commit to main**
4. Click **Publish branch**

---

### Cách 2: Dùng Command Line

```bash
# 1. Di chuyển vào thư mục web
cd "C:\Users\MSI PC\OneDrive\Máy tính\ỨNG ỤNGD\web_hoadon"

# 2. Khởi tạo Git
git init

# 3. Thêm tất cả file
git add .

# 4. Commit
git commit -m "Initial commit"

# 5. Thêm remote (thay YOUR_USERNAME bằng username GitHub của bạn)
git remote add origin https://github.com/YOUR_USERNAME/hoadon-manager.git

# 6. Push lên GitHub
git push -u origin main
```

---

## 4. DEPLOY TRÊN RENDER.COM

### Bước 4.1: Đăng ký Render
1. Mở https://render.com
2. Click **Sign Up**
3. Chọn **Continue with GitHub** (đăng nhập bằng GitHub)
4. Cho phép truy cập GitHub

### Bước 4.2: Tạo Web Service
1. Trên trang Render Dashboard, click **"+" New"**
2. Chọn **Web Service**
3. Kết nối GitHub:
   - **Connect a GitHub account** → chọn tài khoản
   - Tìm và chọn repository `hoadon-manager`
4. Cấu hình service:

| Trường | Giá trị |
|---------|---------|
| **Name** | `hoadon-manager` |
| **Region** | Singapore |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | **Free** |

### Bước 4.3: Environment Variables
Click **Add Environment Variable**:
- **Key:** `SECRET_KEY`
- **Value:** (nhập một chuỗi ngẫu nhiên, VD: `mysecretkey123456`)

### Bước 4.4: Deploy
1. Click **Create Web Service**
2. Chờ quá trình deploy (~2-5 phút)
3. Khi xong, sẽ thấy URL: `https://hoadon-manager.onrender.com`

---

## 5. SAU KHI DEPLOY

### Lần đầu tiên:
1. Mở URL (VD: `https://hoadon-manager.onrender.com`)
2. Trang sẽ ngủ (sleep) → chờ ~30-60 giây để wake up
3. Sau khi wake up, sẽ thấy trang đăng nhập

### Đăng nhập lần đầu:
- **Username:** `admin`
- **Password:** `admin123`

### Đổi mật khẩu admin:
1. Đăng nhập
2. Click avatar → **Đổi mật khẩu**
3. Nhập mật khẩu mới

---

## 6. CÁCH SỬ DỤNG

### Truy cập:
- **Mỗi ngày đầu tiên:** Nhấn URL → chờ wake up ~30-60 giây
- **Lần sau trong ngày:** Truy cập ngay lập tức
- **Sau 15 phút không dùng:** Server ngủ lại

### Tạo tài khoản kế toán:
1. Đăng nhập admin
2. Vào **Người dùng** → **Thêm người dùng**
3. Nhập username, password, chọn vai trò **kế toán**

### Các trang:
| Trang | Mô tả |
|-------|-------|
| **Trang chủ** | Tổng quan, thống kê |
| **Hóa đơn** | Tạo, xem, sửa, xóa hóa đơn |
| **Tài chính** | Doanh thu, chi phí theo tháng |
| **Báo cáo** | Xem và xuất Excel theo khoảng ngày |
| **Người dùng** | Quản lý tài khoản (chỉ admin) |

---

## XỬ LÝ SỰ CỐ

### Lỗi "Application failed to respond"
- Server đang ngủ → chờ thêm 30-60 giây
- Hoặc truy cập lại URL

### Lỗi "Database locked"
- Chỉ có 1 người dùng SQLite tại 1 thời điểm
- Nếu 2 người cùng dùng → có thể bị xung đột

### Muốn nâng cấp lên trả phí
- Render Hobby: $7/tháng (luôn online, không ngủ)
- Railway: $5/tháng

---

## LƯU Ý QUAN TRỌNG

### Về dữ liệu:
- Dữ liệu lưu trên **Render Free**: Server bị xóa sau **90 ngày không dùng**
- **Khuyến nghị**: Dùng thường xuyên để tránh bị xóa
- **Backup**: Xuất Excel thường xuyên để lưu trữ

### Bảo mật:
- Đổi mật khẩu admin ngay sau khi deploy
- Không chia sẻ tài khoản admin
- Repository nên để **Private**

---

## LIÊN HỆ HỖ TRỢ

Nếu gặp lỗi, hãy gửi ảnh chụp lỗi cho tôi để hỗ trợ!

---

**Chúc bạn thành công!** 🚀
