# AR Intelligence Nexus 🚀

> **Executive Accounts Receivable Command Center** — Hệ thống Dashboard phân tích công nợ (AR) thời gian thực, được xây dựng theo kiến trúc Client-Server hiện đại, tối ưu cho triển khai mạng nội bộ (LAN).

---

## 📐 Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                        MẠNG NỘI BỘ (LAN)                        │
│                                                                  │
│  [Máy con / Điện thoại]                                         │
│    Browser → http://192.168.20.55:3000                          │
│                │                                                 │
│                ▼                                                 │
│  ┌─────────────────────────┐                                     │
│  │  FRONTEND (Next.js :3000)│                                   │
│  │  React 19 + TailwindCSS │                                     │
│  │  Proxy /api/* → :8000  │                                     │
│  └────────────┬────────────┘                                     │
│               │ (nội bộ server - không lộ ra ngoài)             │
│               ▼                                                  │
│  ┌─────────────────────────┐                                     │
│  │  BACKEND (FastAPI :8000) │                                   │
│  │  Python + DuckDB        │                                     │
│  └────────────┬────────────┘                                     │
│               │                                                  │
│               ▼                                                  │
│  ┌─────────────────────────┐                                     │
│  │  ar_dashboard.duckdb    │  ← Columnar OLAP database          │
│  └─────────────────────────┘                                     │
└─────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc vàng về bảo mật:** Máy con trong mạng LAN chỉ được phép liên lạc với cổng **3000** (Frontend). Cổng **8000** (Backend) ẩn hoàn toàn — Next.js proxy ngầm mọi request `/api/*` về backend mà không lộ địa chỉ ra bên ngoài.

---

## 📁 Cấu trúc thư mục

```
TOOLS-AR/
├── backend/
│   ├── main.py                    # FastAPI app factory + routing
│   └── app/
│       ├── config/
│       │   ├── constants.py       # Hằng số tên cột, màu sắc UI
│       │   └── settings.py        # Đường dẫn thư mục runtime
│       ├── data/
│       │   ├── db.py              # Kết nối DuckDB, ETL vào DB, Upsert
│       │   ├── etl.py             # Đọc file, làm sạch, ánh xạ AR person
│       │   └── kpi.py             # Tính KPI, bộ lọc, dữ liệu xu hướng
│       ├── charts/
│       │   └── trend.py           # Dựng biểu đồ Plotly
│       └── models/
│           └── schema.py          # clean_columns(), validate_mapping()
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── layout.tsx         # Root layout, font Geist
│       │   ├── page.tsx           # Trang Dashboard chính (toàn bộ UI)
│       │   └── globals.css        # Design system: Glassmorphism CSS
│       └── components/
│           └── Plot.tsx           # Wrapper Plotly với SSR-safe dynamic import
│
├── backend/data/
│   ├── imports/                   # Thư mục nhận file AR data upload
│   └── mapping/                   # Chứa assign_ar_team.xlsx
│
├── ar_dashboard.duckdb            # Database chính (tự động tạo khi chạy)
├── start_backend.bat              # Script khởi động Backend (Windows)
├── start_frontend.bat             # Script khởi động Frontend (Windows)
├── requirements.txt               # Thư viện Python
└── .gitignore
```

---

## 🔄 Luồng dữ liệu end-to-end

### Bước 1: Upload File

```
Người dùng chọn file → POST /api/upload
                           │
                           ├── file tên "assign_ar_team*" → lưu vào backend/data/mapping/
                           └── file khác (AR Data)       → lưu vào backend/data/imports/
                                                              → gọi process_file()
```

### Bước 2: Pipeline ETL (trong `etl.py`)

```
process_file(filepath)
    │
    ├─ 1. ĐỌC FILE
    │   ├── .csv  → pl.read_csv()
    │   └── .xlsx → read_excel_sheet()  [thử lần lượt: "Raw data", "Sheet1", ...]
    │
    ├─ 2. TRÍCH XUẤT HEADER (extract_headers)
    │   └── Quét 10 dòng đầu, tìm dòng có "cust" hoặc "sales person"
    │       → dùng dòng đó làm header, bỏ tất cả dòng phía trên
    │
    ├─ 3. LÀM SẠCH CỘT (standardize_columns)
    │   ├── clean_columns(): lowercase + snake_case + bỏ ký tự đặc biệt
    │   ├── rename_map   : đổi tên cột về chuẩn nội bộ (vd: "Total Amt" → "total_amt_overdue")
    │   ├── _heal_date_corrupted_columns(): FIX LỖI EXCEL DATE
    │   │   └── Excel tự chuyển "7 - 13" → "2026-07-13" hoặc serial "46216"
    │   │       → Dùng vị trí tương đối so với cột neo "0_-_6" để đặt lại tên đúng
    │   └── Loại bỏ cột rác còn tên dạng ngày (yyyy-mm-dd)
    │
    ├─ 4. TẢI DANH SÁCH PHÂN BỔ (_load_mapping_df)
    │   └── Đọc mapping/assign_ar_team.xlsx
    │       → Tương tự pipeline ETL nhỏ (extract_headers + standardize_columns)
    │       → unique(subset=["sales_person_code"]) : loại bỏ dòng trùng lặp
    │
    ├─ 5. KIỂM TRA CHÉO (validate_mapping)
    │   └── So sánh tập mã Sales Person trong data với mapping
    │       → Trả về danh sách missing_codes (chưa được gán AR Person)
    │
    ├─ 6. KHAI THÁC DỮ LIỆU (JOIN)
    │   └── enriched_df = raw_df.join(mapping_df, on="sales_person_code", how="left")
    │       → Gán AR Person vào từng dòng theo Sales Person Code
    │       → fill_null("Unassigned") cho những mã chưa được ánh xạ
    │
    ├─ 7. CAST KIỂU SỐ
    │   └── Ép kiểu tất cả cột aging + bal_due + total_amt_overdue → Float64
    │
    └─ 8. XÁC ĐỊNH SNAPSHOT
        └── get_snapshot_info(filename)
            ├── Tìm MONTH_N trong tên file → snapshot_type = "monthly"
            ├── Tìm DAY_N    trong tên file → snapshot_type = "daily"
            └── Gắn timestamp theo tháng/ngày tương ứng (năm mặc định: 2026)
```

### Bước 3: Lưu vào Database (`db.py`)

```
load_data(raw_df, fact_df, file_name)
    │
    ├─ UPSERT LOGIC
    │   └── Nếu snapshot_id (= tên file) đã tồn tại → xóa records cũ trước khi insert
    │
    ├─ AUTO-CLEANUP: Nếu import "monthly" → tự động xóa tất cả "daily" cùng tháng
    │
    ├─ INSERT vào raw_ar (dữ liệu gốc) + fact_ar (dữ liệu sau ánh xạ AR)
    │   └── align_and_insert(): Schema Evolution tự động
    │       ├── DROP cột không còn trong schema mới
    │       └── ADD cột mới xuất hiện trong file mới nhất
    │
    └─ XÂY DỰNG DATA MART
        └── mart_filters: lưu sẵn tổ hợp (ar_person, sales_person_code, name)
            → Phục vụ API /filters cực nhanh (vài ms)
```

---

## 🗄️ Cấu trúc Database (DuckDB)

### Bảng `import_history`
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `snapshot_id` | VARCHAR PK | Tên file upload (dùng làm ID duy nhất) |
| `file_name` | VARCHAR | Tên file gốc |
| `imported_at` | TIMESTAMP | Thời điểm dữ liệu của kỳ đó (từ tên file) |
| `total_rows` | INTEGER | Số dòng trong file |
| `snapshot_type` | VARCHAR | `"monthly"` hoặc `"daily"` |

### Bảng `fact_ar` (bảng chính phân tích)
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `cust_id` | VARCHAR | Mã khách hàng |
| `name` | VARCHAR | Tên khách hàng |
| `sales_person_code` | VARCHAR | Mã nhân viên kinh doanh |
| `ar_person` | VARCHAR | Tên nhân viên AR phụ trách (sau ánh xạ) |
| `term` | VARCHAR | Điều khoản thanh toán |
| `0_-_6` | FLOAT | Công nợ quá hạn 0–6 ngày |
| `7_-_13` | FLOAT | Công nợ quá hạn 7–13 ngày |
| `14_-_20` | FLOAT | Công nợ quá hạn 14–20 ngày |
| `21_-_29` | FLOAT | Công nợ quá hạn 21–29 ngày |
| `30_-_37` | FLOAT | Công nợ quá hạn 30–37 ngày |
| `38_-_45` | FLOAT | Công nợ quá hạn 38–45 ngày |
| `45_up` | FLOAT | Công nợ quá hạn trên 45 ngày |
| `60_up` | FLOAT | Công nợ quá hạn trên 60 ngày |
| `bal_due` | FLOAT | **Tổng công nợ** (Balance Due) |
| `total_amt_overdue` | FLOAT | **Tổng tiền quá hạn** (các cột aging cộng lại) |
| `cr_limit` | FLOAT | Hạn mức tín dụng |
| `snapshot_id` | VARCHAR FK | Liên kết với import_history |

> **Quan hệ:** `total_amt_overdue ≈ 0_-_6 + 7_-_13 + 14_-_20 + 21_-_29 + 30_-_37 + 38_-_45 + 45_up + 60_up`

### Bảng `mart_filters` (Data Mart tăng tốc UI)
| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `snapshot_id` | VARCHAR | FK → import_history |
| `ar_person` | VARCHAR | Tên AR Person |
| `sales_person_code` | VARCHAR | Mã Sales Person |
| `name` | VARCHAR | Tên khách hàng |

---

## 📊 Công thức KPI

| KPI hiển thị | Công thức SQL | Ghi chú |
|--------------|---------------|---------|
| **Total AR Amount** | `SUM(bal_due)` | Tổng toàn bộ công nợ đang có |
| **Total Balance Overdue** | `SUM(total_amt_overdue)` | Tổng tiền đã quá hạn thanh toán |
| **% Overdue** | `SUM(total_amt_overdue) / SUM(bal_due)` | Tỉ lệ công nợ quá hạn / tổng công nợ |
| **Total Customers** | `COUNT(DISTINCT name)` | Số khách hàng duy nhất |

---

## 🔌 REST API — Backend (FastAPI :8000)

| Endpoint | Method | Body | Trả về |
|----------|--------|------|--------|
| `/api/ping` | GET | — | `{"status":"ok"}` |
| `/api/snapshot` | GET | — | `{"snapshot_id": "..."}` — ID của lần import mới nhất |
| `/api/upload` | POST | `multipart/form-data` files[] | `{success, success_count, errors[]}` |
| `/api/metrics` | POST | `{snapshot_id, filters}` | `{total_ar, balance_overdue, pct_overdue, total_customers}` |
| `/api/trend` | POST | `{snapshot_id, filters}` | `[{title, fig_json}]` — mảng 10 biểu đồ Plotly JSON |
| `/api/data` | POST | `{snapshot_id, filters}` | `[{...row...}]` — tối đa 1000 dòng |
| `/api/filters` | POST | `{snapshot_id, filters}` | `{ar_person[], sales_person_code[], name[]}` |

### Cấu trúc `filters` payload

```json
{
  "snapshot_id": "AR_DATA_MONTH_4.xlsx",
  "filters": {
    "ar_person": [],
    "sales_person_code": ["CARLOS", "KANLY"],
    "name": []
  }
}
```

- **Mảng rỗng `[]`** = chọn tất cả (không filter)
- **`["__NONE__"]`** = không chọn gì (kết quả rỗng)
- **Mảng có giá trị** = lọc theo IN(...)

---

## 🎛️ Logic Bộ lọc Cross-filtering (Frontend)

Bộ lọc hoạt động theo cơ chế **cascading dependency** (phụ thuộc tầng):

```
AR Person (level 1 - Root)
    └── Sales Person (level 2 - phụ thuộc AR Person đang chọn)
            └── Customer (level 3 - phụ thuộc AR Person + Sales Person đang chọn)
```

**Nguyên tắc hoạt động của nút ALL:**
- `filters[category] = []` → **ALL** đang được chọn (không có ràng buộc)
- `filters[category] = ["A", "B"]` → chỉ chọn A và B
- `filters[category] = ["__NONE__"]` → không chọn gì (trường hợp bỏ chọn hết)

---

## 📈 Biểu đồ Xu hướng (10 charts)

Dữ liệu trend lấy từ **7 kỳ gần nhất** (`import_history ORDER BY imported_at DESC LIMIT 7`), group theo ngày và loại snapshot. Gồm các biểu đồ cột (Bar Chart):

| # | Tiêu đề | Cột dữ liệu | Màu |
|---|---------|-------------|-----|
| 1 | Balance Overdue Amount | `total_amt_overdue` | Blue |
| 2 | % Overdue / Balance Overdue | `pct_overdue` | Blue |
| 3 | Total AR Amount | `bal_due` | Blue |
| 4 | Overdue 60 UP | `60_up` | Orange |
| 5 | Overdue 45 UP | `45_up` | Orange |
| 6 | Overdue 38 - 45 | `38_-_45` | Orange |
| 7 | Overdue 30 - 37 | `30_-_37` | Blue |
| 8 | Overdue 21 - 29 | `21_-_29` | Blue |
| 9 | Overdue 14 - 20 | `14_-_20` | Blue |
| 10 | Overdue 7 - 13 | `7_-_13` | Blue |
| 11 | Overdue 0 - 6 | `0_-_6` | Blue |

> **Fix lỗi Excel Date:** Cột `7 - 13` bị Excel tự động convert thành ngày "July 13". Hệ thống phát hiện bằng cách kiểm tra vị trí tương đối so với cột neo `0_-_6` và tự đặt lại tên đúng.

---

## 🎨 Thiết kế UI/UX (Frontend)

**Design System** được định nghĩa trong `globals.css`:

| Class | Mô tả |
|-------|-------|
| `.glass-container` | Container chính, Glassmorphism (`backdrop-filter: blur(25px)`) |
| `.metric-card` | Thẻ KPI với hover animation (`translateY(-5px)`) |
| `.chart-container` | Khung biểu đồ với hover lift effect |
| `.btn-primary` | Nút chính gradient Blue |
| `.btn-secondary` | Nút phụ trắng viền |
| `.tab-btn` / `.tab-btn.active` | Tab điều hướng |

**Font:** Geist Sans (Google) + Plus Jakarta Sans — load qua `next/font/google`

**Bảng Detail Data:** Tích hợp `overflow-x-auto + max-h-[600px]` với `thead sticky top-0` để Sticky Header hoạt động đúng khi cuộn hàng ngàn dòng.

**Fix lỗi CSS Stacking Context:** Modal Filter được đặt **ngoài** thẻ `<main>` (thẻ có `backdrop-filter`) để tránh bị CSS containing block bug làm lệch `position: fixed`.

---

## ⚙️ Cài đặt & Vận hành

### Yêu cầu
- Python 3.10+
- Node.js 18+ (đã cài sẵn `C:\Program Files\nodejs`)
- Git

### Lần đầu cài đặt

```bash
# 1. Backend: Tạo môi trường ảo và cài thư viện
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 2. Frontend: Cài Node dependencies
cd frontend
npm install
cd ..
```

### Khởi chạy hàng ngày (Dễ nhất)

Click đúp vào **2 file** tại thư mục gốc theo thứ tự:
1. `start_backend.bat` → Cửa sổ đen hiện lên, giữ nguyên
2. `start_frontend.bat` → Cửa sổ đen thứ hai, giữ nguyên

Sau đó mở trình duyệt:
- **Trên máy chủ:** `http://localhost:3000`
- **Máy khác cùng mạng LAN:** `http://192.168.20.55:3000`

### Tắt hệ thống
Bấm `Ctrl + C` trên từng cửa sổ đen hoặc đóng chúng lại.

---

## 📂 Quy ước đặt tên file Upload

Hệ thống tự động xác định kỳ dữ liệu từ tên file:

| Tên file | Loại | Thời điểm gán |
|----------|------|---------------|
| `AR_DATA_MONTH_1.xlsx` | monthly | 31/01/2026 23:59:59 |
| `AR_DATA_MONTH_4.xlsx` | monthly | 30/04/2026 23:59:59 |
| `AR_DATA_MONTH_4_DAY_15.xlsx` | daily | 15/04/2026 12:00:00 |
| `assign_ar_team.xlsx` | mapping | Lưu vào `mapping/` (không xử lý ETL) |

> **Quy tắc Auto-cleanup:** Khi import file `monthly` của tháng N, hệ thống **tự động xóa** toàn bộ các bản ghi `daily` cùng tháng đó khỏi database để tránh tính đúp.

---

## ⚠️ Xử lý lỗi & Các trường hợp đặc biệt

| Vấn đề | Nguyên nhân | Giải pháp trong code |
|--------|-------------|---------------------|
| Cột `7 - 13` biến thành ngày | Excel auto-convert | `_heal_date_corrupted_columns()` dùng vị trí cột |
| AR Person hiển thị "Unassigned" | File mapping chưa có hoặc upload sai thư mục | `fill_null("Unassigned")` + lưu đúng vào `mapping/` |
| Dữ liệu bị nhân bản (đúp dòng) | File `assign_ar_team` có nhiều dòng trùng cùng mã Sales | `.unique(subset=["sales_person_code"])` |
| Plotly crash trên Next.js | Plotly cố dùng `window` khi SSR | `next/dynamic` với `{ ssr: false }` |
| Modal Filter bị lệch màn hình | CSS `backdrop-filter` tạo containing block | Đặt Modal ngoài `<main>` |
| `NaN` / `Infinity` trong JSON | Chia cho 0 hoặc giá trị rỗng | `_sanitize_metrics()` trong `main.py` |
| Port 8000 đã bị chiếm | Tiến trình cũ đang chạy ngầm | `taskkill /F /PID <pid>` hoặc restart máy |

---

## 🔒 Bảo mật & Network

- Backend `allow_origins=["*"]` — phù hợp môi trường mạng nội bộ khép kín
- Frontend proxy ẩn địa chỉ backend: máy con không biết cổng 8000 tồn tại
- File `.env` chứa `ALLOWED_DEV_ORIGINS` để Next.js không chặn request từ IP LAN

---

## 🛠️ Stack công nghệ

| Layer | Công nghệ | Phiên bản | Vai trò |
|-------|-----------|-----------|---------|
| Backend Framework | FastAPI | ≥0.115 | REST API server |
| ASGI Server | Uvicorn | ≥0.30 | HTTP server chạy FastAPI |
| Data Processing | Polars | ≥0.20 | Đọc & xử lý Excel/CSV siêu tốc |
| Database | DuckDB | ≥0.9 | OLAP columnar DB, query phân tích |
| Data Manip | Pandas | ≥2.0 | Tương thích DuckDB `.fetchdf()` |
| Visualization | Plotly | ≥5.18 | Dựng biểu đồ JSON phía Server |
| Excel Engine | fastexcel + openpyxl | — | Đọc file .xlsx |
| Frontend | Next.js | 16.x | React framework + API proxy |
| UI Framework | React | 19.x | Component-based UI |
| Styling | TailwindCSS | v4 | Utility CSS |
| Charts (FE) | react-plotly.js | ≥4.0 | Render biểu đồ từ JSON |
