# userbot_daily_sender.py
# Darhol yuborish o'chirildi — faqat 15:40 da yuboriladi

import asyncio
import aiosqlite
import json
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message

# ------------------- Sozlamalar -------------------
API_ID = 22936295
API_HASH = "2092af84df82745acded1f3a5d1ceeaf"
PHONE_NUMBER = "+998919241285"

TARGET_USERNAME = "@KholikovaShakhina"
DB_FILE = "sent_messages.db"
MEMORY_JSON = "message_memory.json"
MEMORY_XML = "message_memory.xml"

UZB_TIMEZONE = pytz.timezone("Asia/Tashkent")
SEND_HOUR = 8
SEND_MINUTE = 10
# --------------------------------------------------

app = Client("daily_userbot", api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)

# ------------------- DB yaratish va yangilash -------------------
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sent_logs'") as cursor:
            table_exists = await cursor.fetchone()

        if not table_exists:
            await db.execute("""
                CREATE TABLE sent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_username TEXT NOT NULL,
                    message_text TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    is_sent INTEGER DEFAULT 0
                )
            """)
            await db.commit()
        else:
            async with db.execute("PRAGMA table_info(sent_logs)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
            if 'is_sent' not in columns:
                await db.execute("ALTER TABLE sent_logs ADD COLUMN is_sent INTEGER DEFAULT 0")
                await db.commit()

# ------------------- Xotirani saqlash -------------------
def save_to_memory(username: str, message: str, sent_at: str):
    try:
        with open(MEMORY_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []
    data.append({"username": username, "message": message, "sent_at": sent_at})
    with open(MEMORY_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    try:
        tree = ET.parse(MEMORY_XML)
        root = tree.getroot()
    except FileNotFoundError:
        root = ET.Element("messages")
    msg = ET.SubElement(root, "message")
    ET.SubElement(msg, "username").text = username
    ET.SubElement(msg, "text").text = message
    ET.SubElement(msg, "sent_at").text = sent_at
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(MEMORY_XML, encoding="utf-8", xml_declaration=True)

# ------------------- Faqat 15:40 da yuborish -------------------
async def daily_sender():
    global TARGET_USERNAME
    await init_db()
    while True:
        now = datetime.now(UZB_TIMEZONE)
        target_time = UZB_TIMEZONE.localize(datetime.combine(now.date(), time(SEND_HOUR, SEND_MINUTE)))

        # Faqat 15:40 da yuborish
        if now.hour == SEND_HOUR and now.minute == SEND_MINUTE and now.second < 10 and TARGET_USERNAME:
            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute("SELECT message_text FROM sent_logs ORDER BY id DESC LIMIT 1") as cursor:
                    row = await cursor.fetchone()

            if row:
                message_text = row[0]
                try:
                    await app.send_message(TARGET_USERNAME, message_text)
                    sent_at = datetime.now(UZB_TIMEZONE).isoformat()
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute(
                            "INSERT INTO sent_logs (target_username, message_text, sent_at, is_sent) VALUES (?, ?, ?, ?)",
                            (TARGET_USERNAME, message_text, sent_at, 1)
                        )
                        await db.commit()
                    save_to_memory(TARGET_USERNAME, message_text, sent_at)
                    print(f"[{sent_at}] @{TARGET_USERNAME} ga yuborildi.")
                except Exception as e:
                    print(f"Yuborishda xato: {e}")
                    async with aiosqlite.connect(DB_FILE) as db:
                        await db.execute(
                            "INSERT INTO sent_logs (target_username, message_text, sent_at, is_sent) VALUES (?, ?, ?, ?)",
                            (TARGET_USERNAME, message_text, datetime.now(UZB_TIMEZONE).isoformat(), 0)
                        )
                        await db.commit()

            # Keyingi kun
            target_time += timedelta(days=1)

        await asyncio.sleep(60)

# ------------------- Buyruqlar -------------------
@app.on_message(filters.private & filters.me)
async def handle_commands(client: Client, message: Message):
    global TARGET_USERNAME
    text = (message.text or message.caption or "").strip()

    if text.startswith("/set"):
        try:
            username = text.split(maxsplit=1)[1].lstrip("@")
            user = await client.get_users(username)
            TARGET_USERNAME = user.username or str(user.id)
            await message.edit(f"@{username} o'rnatildi. Xabar faqat 15:40 da yuboriladi.")
        except:
            await message.edit("Foydalanuvchi topilmadi.")

    elif text.startswith("/send"):
        if not TARGET_USERNAME:
            await message.edit("Avval `/set @username` buyrug'i bilan foydalanuvchi o'rnating.")
            return
        try:
            msg_text = text.split(maxsplit=1)[1]
            sent_at = datetime.now(UZB_TIMEZONE).isoformat()
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute(
                    "INSERT INTO sent_logs (target_username, message_text, sent_at, is_sent) VALUES (?, ?, ?, ?)",
                    (TARGET_USERNAME, msg_text, sent_at, 0)
                )
                await db.commit()
            save_to_memory(TARGET_USERNAME, msg_text, sent_at)
            await message.edit(f"Xabar saqlandi. Ertaga 15:40 da yuboriladi.")
        except IndexError:
            await message.edit("Foydalanish: `/send Xabar matni`")

    elif text == "/status":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT COUNT(*) FROM sent_logs WHERE is_sent = 0") as cursor:
                pending = (await cursor.fetchone() or [0])[0]
            async with db.execute("SELECT COUNT(*) FROM sent_logs WHERE is_sent = 1") as cursor:
                sent = (await cursor.fetchone() or [0])[0]
        await message.edit(f"Yuborilmagan: {pending}\nYuborilgan: {sent}")

    else:
        await message.edit(
            "Buyruqlar:\n"
            "`/set @username` — kimga\n"
            "`/send Xabar` — saqlash\n"
            "`/status` — holat"
        )

# ------------------- Ishga tushirish -------------------
async def main():
    await init_db()
    asyncio.create_task(daily_sender())
    print("Userbot ishga tushdi. Faqat 15:40 da yuboradi.")
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    app.run(main())
