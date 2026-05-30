# 📦 StockPulse — Inventory Management App

A fast, mobile-friendly inventory management system built with Flask, SQLite, Tailwind CSS, and html5-qrcode.

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the app
```bash
python app.py
```

### 3. Open in browser
```
http://localhost:5000
```

For mobile access on the same Wi-Fi network:
```
http://<your-local-ip>:5000
```
Find your IP: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)

> ⚠️ Camera/barcode scanning requires either **localhost** or **HTTPS**. For LAN access, use a tool like [ngrok](https://ngrok.com) to get an HTTPS URL.

---

## 📱 Features

| Page | Description |
|------|-------------|
| **Dashboard** | Stats overview, quick actions, recent products |
| **Add Stock** | Scan barcode with camera, fill details, save to DB |
| **Inventory** | Browse all products, live search, edit inline |
| **Stock Out** | Scan barcode, confirm, reduce qty or delete if last unit |

---

## 🗂 Project Structure

```
inventory_app/
├── app.py                  # Flask backend + SQLite routes
├── inventory.db            # Auto-created SQLite database
├── requirements.txt
├── README.md
└── templates/
    ├── base.html           # Shared layout, nav, toast system
    ├── dashboard.html      # Stats + quick actions
    ├── add_stock.html      # Add product + barcode scanner
    ├── inventory.html      # Product list + edit modal
    └── stock_out.html      # Scan to remove stock
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/products` | Add new product |
| GET | `/api/products/scan/<barcode>` | Lookup by barcode |
| PUT | `/api/products/<id>` | Update product |
| POST | `/api/products/stock-out/<barcode>` | Reduce qty by 1 |
| GET | `/api/stats` | Dashboard statistics |

---

## 🛠 Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (zero config)
- **Frontend**: HTML + Tailwind CSS (CDN) + Vanilla JS
- **Scanner**: html5-qrcode (EAN, UPC, CODE128, QR)
- **Fonts**: Syne + DM Sans (Google Fonts)

---

## 📷 Barcode Formats Supported

- EAN-13 / EAN-8
- UPC-A / UPC-E
- CODE-128 / CODE-39
- QR Code

---

## 💡 Tips

- **Low stock** = 3 or fewer units remaining (shown in orange)
- **Out of stock** = 0 units (product auto-deleted on last stock-out)
- **Duplicate barcodes** are blocked automatically
- Works best in **Chrome on Android** or **Safari on iOS**
