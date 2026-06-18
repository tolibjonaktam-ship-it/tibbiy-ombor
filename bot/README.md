# Shartnoma (dogovor) Telegram boti

Bu bot Telegram orqali **bemor shartnomalarini** to'ldiradi (ism, familiya,
telefon, tashxis, implant, summa va h.k.) va har bir shartnomani avtomatik
**Google Sheets** jadvaliga yangi qator qilib yozadi.

```
Telegram bot  ──►  qadam-baqadam savollar  ──►  Google Sheets jadvali
```

---

## 1-qadam. Telegram bot tokenini olish

1. Telegram'da **@BotFather** ni oching.
2. `/newbot` buyrug'ini yuboring.
3. Botga nom va username bering (username `_bot` bilan tugashi kerak).
4. BotFather sizga **token** beradi, masalan:
   `123456789:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxx`
5. Shu tokenni saqlab qo'ying — keyin `.env` faylga yozasiz.

---

## 2-qadam. Google Sheets jadvalini tayyorlash

1. https://sheets.google.com ga kiring va **yangi jadval** yarating.
2. Jadvalga istalgan nom bering (masalan: `Shartnomalar`).
3. Jadval manzilidan (URL) **ID** ni oling. URL shunday ko'rinadi:
   ```
   https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
                                          └──────── ID ────────────┘
   ```
   Mana shu o'rtadagi qism — `GOOGLE_SHEET_ID`.

> Ustun sarlavhalarini (Qo'shilgan vaqt, Bemor ismi, ...) qo'lda yozish shart
> emas — bot birinchi marta yozishda ularni o'zi qo'shadi.

---

## 3-qadam. Google "service account" yaratish (botni jadvalga ulash)

Bot jadvalga yozishi uchun unga ruxsat kerak. Buning uchun bepul "service
account" ochamiz:

1. https://console.cloud.google.com ga kiring (Google akkaunt bilan).
2. Yuqorida **yangi loyiha** (project) yarating yoki mavjudini tanlang.
3. Qidiruvga **"Google Sheets API"** deb yozib, uni oching va **Enable**
   (yoqish) tugmasini bosing.
4. Chap menyudan **APIs & Services → Credentials** ga o'ting.
5. **Create Credentials → Service account** ni tanlang.
   - Nom bering (masalan: `bot`), **Create and continue → Done**.
6. Yaratilgan service account ustiga bosing → **Keys** bo'limi →
   **Add Key → Create new key → JSON** → **Create**.
7. Kompyuteringizga `.json` fayl yuklab olinadi. Uni `bot/` papkaga ko'chiring
   va nomini **`credentials.json`** qo'ying.
8. Shu JSON faylni oching, ichida `"client_email": "...@....iam.gserviceaccount.com"`
   degan **email** bor. Uni nusxalang.
9. Google Sheets jadvalingizni oching → **Share (Ulashish)** → shu email'ni
   qo'shing va **Editor (Muharrir)** huquqini bering. **Send/Share**.

> ⚠️ `credentials.json` — bu maxfiy kalit. Uni hech kimga bermang va GitHub'ga
> yuklamang (`.gitignore` allaqachon uni bloklaydi).

---

## 4-qadam. Sozlamalarni yozish (.env)

`bot/` papkada `.env.example` faylidan nusxa olib, `.env` deb nomlang va
to'ldiring:

```bash
cp .env.example .env
```

`.env` ichi:

```
BOT_TOKEN=123456789:AAH-bu-yerga-tokeningiz
GOOGLE_SHEET_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_WORKSHEET_NAME=
```

---

## 5-qadam. Ishga tushirish

```bash
cd bot
pip install -r requirements.txt
python bot.py
```

Hammasi to'g'ri bo'lsa terminalda **"Bot ishga tushdi"** chiqadi.

Endi Telegram'da botingizni oching va **/start** ni bosing. Bot savollarni
ketma-ket beradi, siz javob yozasiz, oxirida ma'lumotlar Google Sheets'ga
tushadi.

---

## Bot buyruqlari

| Buyruq    | Vazifasi                          |
|-----------|-----------------------------------|
| `/start`  | Yangi shartnoma to'ldirishni boshlash |
| `/bekor`  | To'ldirishni bekor qilish         |
| `/yordam` | Yordam                            |

Ixtiyoriy (majburiy bo'lmagan) savollarda **"⏭ O'tkazib yuborish"** tugmasi
chiqadi — bossangiz, o'sha maydon bo'sh qoldiriladi.

---

## To'planadigan ma'lumotlar (maydonlar)

Qo'shilgan vaqt, Bemor ismi, Familiyasi, Otasining ismi, Tug'ilgan sana,
Telefon, Manzil, Tashxis, Implant/mahsulot, Shifokor, Operatsiya sanasi,
Summa, Izoh, Operator (kim kiritgani).

**Maydonlarni o'zgartirish:** `bot.py` faylidagi `FIELDS` ro'yxatini va
`sheets.py` faylidagi `HEADERS` ro'yxatini tahrirlang (ikkalasi mos
bo'lishi kerak).

---

## Tez-tez uchraydigan xatoliklar

- **`BOT_TOKEN o'rnatilmagan`** — `.env` faylga tokenni yozmagansiz.
- **`Service account fayli topilmadi`** — `credentials.json` `bot/` papkada
  yo'q yoki nomi noto'g'ri.
- **`PermissionError` / `403`** — jadvalni service account email'iga
  "Editor" qilib ulashmagansiz (3-qadam, 9-band).
- **`SpreadsheetNotFound`** — `GOOGLE_SHEET_ID` noto'g'ri.
