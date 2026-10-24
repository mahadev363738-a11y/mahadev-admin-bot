# Telegram Firebase Bot Hosting Instructions

## Option 1: Render.com Par Free 24/7 Host Karein (Recommended)

1. Github par new repository banayein aur `python_bot` folder ke saare files (`telegram_bot.py`, `requirements.txt`) upload karein.
2. [Render.com](https://render.com) par free account banayein.
3. Dashboard par **New +** -> **Background Worker** click karein.
4. Connect GitHub repository.
5. Configuration set karein:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python telegram_bot.py`
6. Environment Variables section me add karein:
   - `TELEGRAM_BOT_TOKEN` = `<Aapka Telegram Bot Token>`
7. **Create Background Worker** par click karein. Bot 24/7 online ho jayega!

---

## Option 2: Termux / Android Phone Par Run Karein

1. Termux app open karein:
   ```bash
   pkg update && pkg upgrade -y
   pkg install python git -y
   pip install python-telegram-bot requests firebase-admin
   ```
2. Token set karein:
   ```bash
   export TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
   ```
3. Run karein:
   ```bash
   python telegram_bot.py
   ```
