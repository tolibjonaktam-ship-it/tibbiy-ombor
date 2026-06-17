# MedStock ERP

Travmatologiya va ortopediya implantlari savdosi uchun **ombor, sotuv va qaytarish** tizimi.

Texnik topshiriqdagi (`MedStock ERP`) barcha asosiy funksiyalar bitta, oson ishga
tushiriladigan ilovada amalga oshirilgan: **Flask + SQLite + HTML** (og'ir
o'rnatishlarsiz, bitta buyruq bilan ishlaydi).

## Imkoniyatlar

- **Mahsulotlar bazasi** — kod, artikul, nomi, o'lchov birligi, qoldiq, tannarx,
  sotuv narxi, sotilgan/qaytarilgan son, omborda turgan kunlar.
- **Kontragentlar bazasi** — nomi, menejer, status, sklad, telefon.
- **Operatsiyalar moduli** — texnik topshiriqdagi barcha ustunlar bilan:
  - Artikul tanlanganda **avtomatik to'ldirish** (Наименование, Остаток, Себестоимость, Цена продажи).
  - Formulalar: `Продажа = Отгр − Возврат`, `Сумма продаж = Продажа × Цена`,
    `costAmount = Продажа × Себестоимость`.
  - Statuslar: `Отправлен` (→ dата отгр), `Продажа`/`Возврат` (→ dата продаж).
  - Ombor qoldig'i: `newStock = currentStock − Отгр + Возврат`.
- **Dashboard** — jami mahsulotlar, jami qoldiq, bugungi/oylik sotuv, qaytarilgan, foyda.
- **Menejer KPI** — sotilgan son, sotuv summasi, qaytarilgan, foyda va **TOP 10 menejer**.
- **Hisobotlar** — Sotuv, Qaytarish va Ombor hisoboti (PDF chiqarish — chop etish orqali).
- **Foydalanuvchilar** — `Admin` va `Menejer` rollari, **JWT** (HMAC) autentifikatsiya.
  Menejer faqat o'z operatsiyalarini ko'radi; mahsulot qo'shish/o'chirish faqat admin.
- **Excel import/export** (CSV — Excel ochadi), **PDF export** (chop etish), **audit log**
  (o'zgarishlar tarixi), tez qidiruv va dropdownlar.

## Ishga tushirish (lokal)

```bash
pip install -r requirements.txt
python server.py
```

Brauzerda oching: **http://localhost:5000**

Standart kirish:

| Login | Parol    | Rol   |
|-------|----------|-------|
| admin | admin123 | Admin |

> Birinchi kirishdan so'ng admin paroli almashtirilishi tavsiya etiladi
> (yangi admin yaratib, eskisini o'chirish orqali).

## Docker bilan

```bash
docker build -t medstock-erp .
docker run -d -p 5000:5000 -v $(pwd)/data:/app medstock-erp
```

`MEDSTOCK_SECRET` muhit o'zgaruvchisi orqali JWT maxfiy kalitini o'rnating
(production uchun majburiy):

```bash
docker run -d -p 5000:5000 -e MEDSTOCK_SECRET="uzun-tasodifiy-kalit" medstock-erp
```

## Ma'lumotlar bazasi

SQLite fayli `ombor.db` avtomatik yaratiladi. Zaxira nusxa olish uchun shu
faylni nusxalash kifoya.
