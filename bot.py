import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GH_PAT = os.getenv("GH_PAT")
REPO = os.getenv("REPO_INFO") # username/repository

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! کانفیگ‌ها یا لینک‌های ساب خود را ارسال کنید تا ساب‌اسکریپشن ساخته شود.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    urls = update.message.text.strip()
    await update.message.reply_text("⏳ در حال ساخت ساب‌اسکریپشن...")
    
    res = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/main.yml/dispatches",
        headers={"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"},
        json={"ref": "main", "inputs": {"sub_type": "Raw", "urls": urls, "custom_name": "ArsenVPN", "repo_info": REPO}}
    )
    if res.status_code == 204:
        await update.message.reply_text("✨ ساب با موفقیت ساخته شد! بعد از چند ثانیه در پنل وب قابل مشاهده است.")
    else:
        await update.message.reply_text("❌ خطا در ارتباط با گیت‌هاب.")

if __name__ == "__main__":
    if TOKEN:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.run_polling()