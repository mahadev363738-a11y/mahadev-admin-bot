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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

DEVICE_KEYS = {
    "device", "devices", "deviceid", "device_id",
    "model", "battery", "status", "lastseen",
    "last_seen", "manufacturer", "platform",
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

    response = requests.get(
        endpoint,
        timeout=15,
        headers={"Accept": "application/json"},
    )

    if response.status_code in (401, 403):
        raise PermissionError(
            "Database private hai ya read permission nahi hai."
        )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict) and "error" in data:
        raise ValueError(str(data["error"]))

    return data


def find_records(data, path="$", depth=0, results=None):
    if results is None:
        results = []

    if depth > 8 or len(results) >= 30:
        return results

    if isinstance(data, dict):
        normalized_keys = {
            str(key).lower().replace("-", "").replace(" ", "")
            for key in data
        }

        device_like = (
            any(
                key in normalized_keys
                for key in ("device", "devices", "deviceid", "device_id")
            )
            or any(
                key.replace("_", "") in {
                    "model", "battery", "manufacturer",
                    "lastseen", "platform"
                }
                for key in normalized_keys
            )
        )

        if device_like:
            results.append((path, data))
            if len(results) >= 30:
                return results

        for key, value in data.items():
            child_path = f"{path}/{key}"
            find_records(value, child_path, depth + 1, results)

    elif isinstance(data, list):
        for index, value in enumerate(data):
            find_records(
                value, f"{path}/{index}", depth + 1, results
            )

    return results


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Firebase Device Inspector\n\n"
        "Apne authorized Firebase Realtime Database ka "
        "HTTPS URL bhejo.\n\n"
        "Example command:\n"
        "/scan https://YOUR-PROJECT-default-rtdb.firebaseio.com\n\n"
        "Sirf URL se private database access nahi milega."
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

    await update.message.reply_text("🔎 Database check ho raha hai...")

    try:
        data = await asyncio.to_thread(fetch_database, url)

        if data is None:
            await update.message.reply_text(
                "Database empty hai ya root par data nahi hai."
            )
            return

        records = find_records(data)

        if not records:
            await update.message.reply_text(
                "Readable data mila, lekin common device fields "
                "detect nahi hue. Database ka structure check karo."
            )
            return

        for path, record in records[:10]:
            lines = [f"📱 Record path: {path}"]

            for key, value in list(record.items())[:15]:
                if isinstance(value, (str, int, float, bool)):
                    text = str(value)[:150]
                    lines.append(f"{key}: {text}")

            await update.message.reply_text("\n".join(lines))

    except PermissionError as exc:
        await update.message.reply_text(
            f"🔒 {exc}\n"
            "Apne project mein Firebase Authentication ya "
            "authorized service-account access configure karo."
        )
    except requests.RequestException:
        await update.message.reply_text(
            "Network ya HTTP error. Firebase URL check karo."
        )
    except (ValueError, TypeError) as exc:
        await update.message.reply_text(
            f"Database response samajh nahi aaya: {str(exc)[:200]}"
        )
    except Exception as exc:
        print("Error:", repr(exc))
        await update.message.reply_text(
            "Unexpected error occurred."
        )


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = (update.message.text or "").strip()

    if not valid_firebase_url(url):
        await update.message.reply_text(
            "Firebase URL samajh nahi aaya.\n"
            "URL ko /scan ke saath bhejo."
        )
        return

    context.args = [url]
    await scan(update, context)


def main():
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN environment variable set karo!")
        return

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