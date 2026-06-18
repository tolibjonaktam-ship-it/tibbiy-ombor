"""
MedStock - Shartnoma (dogovor) Telegram boti.

Bot foydalanuvchidan bemor ma'lumotlarini qadam-baqadam so'raydi va
tayyor shartnomani Google Sheets jadvaliga yozadi.

Ishga tushirish:
    pip install -r requirements.txt
    # .env faylni to'ldiring (.env.example dan nusxa oling)
    python bot.py

Buyruqlar:
    /start  - yangi shartnoma boshlash
    /bekor  - to'ldirishni bekor qilish
    /yordam - yordam
"""

import logging
import os
from datetime import datetime

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import sheets

# .env faylni o'qish (agar python-dotenv o'rnatilgan bo'lsa)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# To'ldiriladigan maydonlar: (kalit, savol matni, majburiymi)
# Bu ro'yxatni o'zgartirsangiz, sheets.py dagi HEADERS ham mos bo'lishi kerak.
FIELDS = [
    ("ism", "Bemorning ismi?", True),
    ("familiya", "Bemorning familiyasi?", True),
    ("sharif", "Otasining ismi (sharifi)?", False),
    ("tugilgan_sana", "Tug'ilgan sanasi? (masalan: 12.05.1980)", False),
    ("telefon", "Telefon raqami? (masalan: +998901234567)", True),
    ("manzil", "Manzili?", False),
    ("tashxis", "Tashxis (diagnoz)?", False),
    ("implant", "Implant / mahsulot nomi?", False),
    ("shifokor", "Shifokor (vrach)?", False),
    ("operatsiya_sana", "Operatsiya sanasi? (masalan: 20.06.2026)", False),
    ("summa", "Summa (narxi)?", False),
    ("izoh", "Qo'shimcha izoh?", False),
]

SKIP_TEXT = "⏭ O'tkazib yuborish"

# Suhbat holati
COLLECTING = 1


def skip_keyboard():
    """Ixtiyoriy maydonlar uchun "o'tkazib yuborish" tugmasi."""
    return ReplyKeyboardMarkup(
        [[SKIP_TEXT]], resize_keyboard=True, one_time_keyboard=True
    )


async def ask_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Joriy indeksdagi maydon bo'yicha savol beradi."""
    idx = context.user_data["idx"]
    key, question, required = FIELDS[idx]
    nomer = f"{idx + 1}/{len(FIELDS)}"

    if required:
        text = f"({nomer}) {question}"
        markup = ReplyKeyboardRemove()
    else:
        text = f"({nomer}) {question}\n(majburiy emas — tugmani bossangiz o'tkazib yuboriladi)"
        markup = skip_keyboard()

    await update.message.reply_text(text, reply_markup=markup)
    return COLLECTING


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yangi shartnoma to'ldirishni boshlaydi."""
    context.user_data["answers"] = {}
    context.user_data["idx"] = 0
    await update.message.reply_text(
        "📋 Yangi shartnoma (dogovor) to'ldiramiz.\n"
        "Har bir savolga javob yozing. Bekor qilish uchun /bekor."
    )
    return await ask_field(update, context)


async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi javobini saqlaydi va keyingi savolga o'tadi."""
    idx = context.user_data["idx"]
    key, question, required = FIELDS[idx]
    answer = (update.message.text or "").strip()

    if answer == SKIP_TEXT:
        if required:
            await update.message.reply_text("Bu maydon majburiy. Iltimos, qiymat kiriting.")
            return COLLECTING
        answer = ""
    elif required and not answer:
        await update.message.reply_text("Bu maydon majburiy. Iltimos, qiymat kiriting.")
        return COLLECTING

    context.user_data["answers"][key] = answer
    context.user_data["idx"] += 1

    if context.user_data["idx"] < len(FIELDS):
        return await ask_field(update, context)

    return await finish(update, context)


async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yig'ilgan ma'lumotlarni Google Sheets'ga yozadi va xulosani ko'rsatadi."""
    answers = context.user_data["answers"]
    user = update.effective_user
    operator = f"@{user.username}" if user.username else (user.full_name or str(user.id))
    vaqt = datetime.now().strftime("%Y-%m-%d %H:%M")

    # sheets.HEADERS tartibida qator tuzamiz
    row = [
        vaqt,
        answers.get("ism", ""),
        answers.get("familiya", ""),
        answers.get("sharif", ""),
        answers.get("tugilgan_sana", ""),
        answers.get("telefon", ""),
        answers.get("manzil", ""),
        answers.get("tashxis", ""),
        answers.get("implant", ""),
        answers.get("shifokor", ""),
        answers.get("operatsiya_sana", ""),
        answers.get("summa", ""),
        answers.get("izoh", ""),
        operator,
    ]

    # Xulosa matni
    xulosa_qatorlar = ["✅ Shartnoma ma'lumotlari:\n"]
    for (key, question, _), label in zip(FIELDS, sheets.HEADERS[1:-1]):
        qiymat = answers.get(key, "") or "—"
        xulosa_qatorlar.append(f"• {label}: {qiymat}")
    xulosa = "\n".join(xulosa_qatorlar)

    try:
        sheets.append_contract(row)
        await update.message.reply_text(
            xulosa + "\n\n📊 Google Sheets jadvaliga muvaffaqiyatli yozildi.",
            reply_markup=ReplyKeyboardRemove(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Google Sheets'ga yozishda xatolik")
        await update.message.reply_text(
            xulosa
            + "\n\n⚠️ Google Sheets'ga yozishda xatolik yuz berdi:\n"
            + f"{exc}\n\nSozlamalarni (README.md) tekshiring.",
            reply_markup=ReplyKeyboardRemove(),
        )

    await update.message.reply_text("Yangi shartnoma uchun /start ni bosing.")
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """To'ldirishni bekor qiladi."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Bekor qilindi. Qaytadan boshlash uchun /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Bu bot bemor shartnomalarini (dogovor) to'ldirib, "
        "Google Sheets jadvaliga yozadi.\n\n"
        "/start - yangi shartnoma\n"
        "/bekor - to'ldirishni bekor qilish\n"
        "/yordam - shu yordam"
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN o'rnatilmagan. .env faylga Telegram bot tokenini yozing "
            "(@BotFather dan oling). README.md ga qarang."
        )

    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            COLLECTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect)],
        },
        fallbacks=[CommandHandler("bekor", cancel)],
    )

    application.add_handler(conv)
    application.add_handler(CommandHandler("yordam", yordam))

    logger.info("Bot ishga tushdi. To'xtatish uchun Ctrl+C.")
    application.run_polling()


if __name__ == "__main__":
    main()
