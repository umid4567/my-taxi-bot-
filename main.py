import os
import asyncio
import requests
import time
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN SOXTA SERVER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

# --- 1. HAYDOVCHI QABUL QILGANDA VA XABAR BERGANDA KUZATUVCHI ---
async def watch_all_events():
    """Barcha Firebase voqealarini bitta tsiklda kuzatamiz"""
    print("Kuzatuv tizimi ishga tushdi...")
    while True:
        try:
            clean_url = BASE_URL.rstrip('/')
            res = requests.get(f"{clean_url}/orders.json").json() or {}
            
            for uid, data in res.items():
                # A. Haydovchi qabul qilganini aniqlash
                if data.get("status") == "accepted" and not data.get("client_notified"):
                    kuzatish_url = f"{XARITA_LINKI}index.html?order_id={uid}"
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚕 Haydovchini xaritada kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                    ])
                    text = "🚕 **Xushxabar!** Buyurtmangiz qabul qilindi.\n\nHaydovchi yo'lga chiqdi. Pastdagi tugma orqali uni xaritada kuzatishingiz mumkin."
                    try:
                        await bot.send_message(uid, text, reply_markup=kb, parse_mode="Markdown")
                        requests.patch(f"{clean_url}/orders/{uid}.json", json={"client_notified": True})
                    except: pass

                # B. Haydovchi "Yo'ldaman" yoki "Keldim" tugmasini bosganini aniqlash
                notify_type = data.get("client_notify")
                if notify_type and not data.get("msg_sent"):
                    msg_text = "🚕 Haydovchi yo'lga chiqdi, tayyor turing!"
                    if notify_type == "arrived":
                        msg_text = "🏁 Haydovchi yetib keldi, tashqariga chiqishingiz mumkin."
                    
                    try:
                        await bot.send_message(uid, msg_text)
                        requests.patch(f"{clean_url}/orders/{uid}.json", json={"msg_sent": True})
                    except: pass
                        
        except Exception as e:
            print(f"Kuzatuvda xatolik: {e}")
            
        await asyncio.sleep(4)

# --- 2. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish", 
                            web_app=WebAppInfo(url=f"{XARITA_LINKI}driver_db.html?driver_id={uid}"))],
            [KeyboardButton(text="💰 Mening balansim")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, haydovchi {user_data.get('name')}!", reply_markup=kb)

    elif user_data and user_data.get("role") == "client":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
            [KeyboardButton(text="ℹ️ Ma'lumot")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Taksi kerak bo'lsa tugmani bosing.", reply_markup=kb)
    
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Rolingizni tanlang:", reply_markup=kb_start)

# --- 3. ROLNI BOSHQARISH ---
@dp.message(F.text == "🔄 Rolni o'zgartirish")
@dp.message(Command("reset"))
async def reset_user(message: Message):
    uid = message.from_user.id
    requests.delete(f"{BASE_URL}users/{uid}.json")
    await message.answer("🔄 Ma'lumotlaringiz o'chirildi.\n/start bosing.", reply_markup=types.ReplyKeyboardRemove())

@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    requests.put(f"{BASE_URL}users/{uid}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.answer(f"✅ Saqlandi! /start bosing.")
    await callback.answer()

# --- 4. BUYURTMA BERISH (YO'LOVCHI) ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat = round(message.location.latitude, 5)
    lon = round(message.location.longitude, 5)
    full_name = message.from_user.full_name or "Mijoz"
    
    order_data = {
        "lat": lat, "lon": lon, "name": full_name,
        "status": "waiting", "time": time.strftime("%H:%M")
    }
    
    clean_url = BASE_URL.rstrip('/') 
    try:
        requests.put(f"{clean_url}/orders/{uid}.json", json=order_data)
        await message.answer("🚕 Buyurtmangiz yuborildi. Iltimos, haydovchi qabul qilishini kuting...")
        
        # Haydovchilarga bildirishnoma yuborish
        all_users = requests.get(f"{clean_url}/users.json").json() or {}
        for d_id, data in all_users.items():
            if data.get("role") == "driver":
                try:
                    await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤 Yo'lovchi: {full_name}\n🚕 Panelingizni tekshiring!")
                except: continue
    except Exception as e:
        print(f"Xatolik: {e}")

# --- ASOSIY MAIN FUNKSIYASI ---
async def main():
    # Web serverni yurgizamiz
    asyncio.create_task(start_web_server())
    # Barcha kuzatuvlarni bitta vazifada yurgizamiz
    asyncio.create_task(watch_all_events())
    # Bot pollingni boshlaymiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass

