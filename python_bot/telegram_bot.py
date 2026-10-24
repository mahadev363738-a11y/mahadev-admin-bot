import os
import re
import asyncio
from urllib.parse import urlparse
import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Auto-detect PythonAnywhere proxy
PROXY_URL = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
if not PROXY_URL:
    home_dir = os.environ.get("HOME", "")
    if "mahadev" in home_dir or "pythonanywhere" in home_dir or os.path.exists("/home/mahadev123"):
        PROXY_URL = "http://proxy.server:3128"

DEVICE_KEYS = {
    "device", "devices", "deviceid", "device_id",
    "model", "battery", "status", "lastseen",
    "last_seen", "manufacturer", "platform",
    "sim", "sim1", "sim2", "number", "phone", "bank"
}

def valid_firebase_url(url):
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower()

        valid_host = (
            host.endswith(".firebasedatabase.app")
            or host.endswith(".firebaseio.com")
        )

        return (
            parsed.scheme == "https"
            and valid_host
            and not parsed.username
            and not parsed.password
        )
    except Exception:
        return False


def fetch_database(url):
    url = url.strip().rstrip("/")
    endpoint = url + "/.json"

    proxies = None
    if PROXY_URL:
        proxies = {"http": PROXY_URL, "https": PROXY_URL}

    response = requests.get(
        endpoint,
        timeout=15,
        headers={"Accept": "application/json"},
        proxies=proxies,
    )

    if response.status_code in (401, 403):
        raise PermissionError(
            "Database private hai ya read permission nahi hai (.read: false)."
        )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict) and "error" in data:
        raise ValueError(str(data["error"]))

    return data


def find_records(data, path="$", depth=0, results=None):
    if results is None:
        results = []

    if depth > 10 or len(results) >= 50:
        return results

    if isinstance(data, dict):
        normalized_keys = {
            str(key).lower().replace("-", "").replace(" ", "").replace("_", "")
            for key in data
        }

        device_like = (
            any(
                k in normalized_keys
                for k in ("device", "devices", "deviceid", "model", "battery", "status", "sim", "sim1", "number", "phone")
            )
        )

        if device_like:
            results.append((path, data))
            if len(results) >= 50:
                return results

        for key, value in data.items():
            child_path = f"{path}/{key}"
            find_records(value, child_path, depth + 1, results)

    elif isinstance(data, list):
        for index, value in enumerate(data):
            find_records(value, f"{path}/{index}", depth + 1, results)

    return results


def format_record(data, max_lines=25):
    lines = []

    def _recurse(obj, prefix=""):
        if len(lines) >= max_lines:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if len(lines) >= max_lines:
                    break
                if isinstance(v, (str, int, float, bool)):
                    lines.append(f"{prefix}{k}: {v}")
                elif isinstance(v, dict):
                    lines.append(f"{prefix}{k}:")
                    _recurse(v, prefix + "  ")
                elif isinstance(v, list):
                    val_str = ", ".join(map(str, v))[:100]
                    lines.append(f"{prefix}{k}: [{val_str}]")
        elif isinstance(obj, (str, int, float, bool)):
            lines.append(f"{prefix}{obj}")

    _recurse(data)
    return lines


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 MAHADEV ADMIN - Firebase Inspector\n\n"
        "Apne Firebase Realtime Database ka HTTPS URL bhejo.\n\n"
        "Example:\n"
        "https://YOUR-PROJECT-default-rtdb.firebaseio.com\n\n"
        "Ya command:\n"
        "/scan https://YOUR-PROJECT-default-rtdb.firebaseio.com"
    )


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/scan https://YOUR-PROJECT-default-rtdb.firebaseio.com"
        )
        return

    url = context.args[0]

    if not valid_firebase_url(url):
        await update.message.reply_text(
            "Valid Firebase Realtime Database HTTPS URL bhejo."
        )
        return

    await update.message.reply_text("🔎 Database scan ho raha hai...")

    try:
        data = await asyncio.to_thread(fetch_database, url)

        if data is None:
            await update.message.reply_text(
                "Database empty hai ya root par data nahi hai."
            )
            return

        records = find_records(data)

        if not records:
            # If no device-like key found, show root data summary
            if isinstance(data, dict):
                lines = ["📱 Root Database Structure:"]
                for k, v in list(data.items())[:10]:
                    if isinstance(v, dict):
                        lines.append(f"📁 /{k} ({len(v)} sub-items)")
                    else:
                        lines.append(f"📄 {k}: {str(v)[:100]}")
                await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(
                    "Database readable hai lekin device structure recognize nahi hua."
                )
            return

        for path, record in records[:15]:
            formatted_lines = format_record(record)
            msg_text = f"📱 Record path: {path}\n" + "\n".join(formatted_lines)
            await update.message.reply_text(msg_text)

    except PermissionError as exc:
        await update.message.reply_text(
            f"🔒 {exc}\n\n"
            "Firebase Console -> Realtime Database -> Rules me check karein:\n"
            '{\n  "rules": {\n    ".read": true,\n    ".write": true\n  }\n}'
        )
    except requests.RequestException as exc:
        await update.message.reply_text(
            f"Network ya HTTP error: {str(exc)[:150]}"
        )
    except (ValueError, TypeError) as exc:
        await update.message.reply_text(
            f"Database response error: {str(exc)[:200]}"
        )
    except Exception as exc:
        print("Error:", repr(exc))
        await update.message.reply_text(
            f"Unexpected error: {str(exc)[:150]}"
        )


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not valid_firebase_url(url):
        await update.message.reply_text(
            "Valid Firebase URL bhejo.\n"
            "Example: https://YOUR-PROJECT-default-rtdb.firebaseio.com"
        )
        return

    context.args = [url]
    await scan(update, context)


def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable set karo!")
        return

    print("Initializing Telegram Bot...")
    if PROXY_URL:
        print(f"Using Proxy: {PROXY_URL}")
        try:
            request = HTTPXRequest(proxy_url=PROXY_URL)
        except TypeError:
            request = HTTPXRequest(proxy=PROXY_URL)
        app = Application.builder().token(BOT_TOKEN).request(request).build()
    else:
        app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)
    )

    print("Bot running. Stop with Ctrl+C.")
    app.run_polling()


if __name__ == "__main__":
    main()