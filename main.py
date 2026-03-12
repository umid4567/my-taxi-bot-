import os
import asyncio
import requests
import math # Masofa hisoblash uchun
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    WebAppInfo,
    ReplyKeyboardRemove
)

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot" 
MAX_RADIUS = 5.0 # Haydovchi va mijoz orasidagi max masofa (km)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYA: Masofani hisoblash (Radius) ---
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Yer radiusi (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 1. ROL TANLANGANDA TELEFON SO'RASH ---
@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    
    requests.patch(f"{BASE_URL}users/{uid}.json", json={
        "role": role, 
        "name": callback.from_user.full_name
    })
    
    kb_phone = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    
    await callback.message.answer(
        f"Siz **{role}** rolingizni tanladingiz.\n\nBog'lanish uchun pastdagi tugmani bosib, telefon raqamingizni yuboring:", 
        reply_markup=kb_phone,
        parse_mode="Markdown"
    )
    await callback.answer()

# --- 2. KONTAKTNI QABUL QILISH ---
@dp.message(F.contact)
async def handle_contact(message: Message):
    uid = message.from_user.id
    phone = message.contact.phone_number
    requests.patch(f"{BASE_URL}users/{uid}.json", json={"phone": phone})
    await message.answer("✅ Rahmat! Telefon raqamingiz saqlandi.\nEndi /start tugmasini bosing.", reply_markup=ReplyKeyboardRemove())

# --- RENDER UCHUN SERVER ---
async def handle(request):
    return web.Response(text="Axi Taxi Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- KUZATUVCHI ---
async def watch_all_events():
    while True:
        try:
            r = requests.get(f"{BASE_URL}orders.json")
            orders = r.json()
            if orders:
                for order_id, data in orders.items():
                    if data.get("status") in ["accepted", "coming"] and data.get("driver_notified_client") is not True:
                        kuzatish_url = f"{XARITA_LINKI}/passenger.html?order_id={order_id}"
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                        ])
                        text = "🚕 **Haydovchi yo'lga chiqdi!**\n\nUni xaritada kuzatishingiz mumkin."
                        try:
                            await bot.send_message(chat_id=order_id, text=text, reply_markup=kb, parse_mode="Markdown")
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"driver_notified_client": True})
                        except: pass
        except: pass
        await asyncio.sleep(4)

# --- START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()
    if user_data and user_data.get("phone"):
        if user_data.get("role") == "driver":
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="🚖 Buyurtmalarni kutish", web_app=WebAppInfo(url=f"{XARITA_LINKI}/driver_db.html?driver_id={uid}"))],
                [KeyboardButton(text="🔄 Rolni o'zgartirish")]
            ], resize_keyboard=True)
            await message.answer(f"Salom haydovchi {user_data.get('name')}!", reply_markup=kb)
        else:
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
                [KeyboardButton(text="🔄 Rolni o'zgartirish")]
            ], resize_keyboard=True)
            await message.answer("Taksi kerak bo'lsa lokatsiya yuboring.", reply_markup=kb)
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Rolingizni tanlang:", reply_markup=kb_start)

# --- BUYURTMA BERISH (RADIUS BILAN) ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude
    
    # 1. Buyurtmani bazaga 'waiting' holatida yozish
    order_data = {
        "lat": lat, "lon": lon, 
        "name": message.from_user.full_name, 
        "status": "waiting",
        "driver_id": None # Hali haydovchi yo'q
    }
    requests.put(f"{BASE_URL}orders/{uid}.json", json=order_data)
    
    await message.answer("🚕 Buyurtma yaqin atrofdagi haydovchilarga yuborildi...")

    # 2. Haydovchilarni saralash va yuborish
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    drivers_sent = 0
    
    for d_id, d_data in all_users.items():
        if d_data.get("role") == "driver":
            # Haydovchining oxirgi lokatsiyasi (taximeter oynasidan yuborib turiladi)
            d_lat = d_data.get("driver_lat")
            d_lon = d_data.get("driver_lon")
            
            # Agar haydovchi koordinatasi bo'lsa, masofani tekshiramiz
            if d_lat and d_lon:
                dist = get_distance(lat, lon, float(d_lat), float(d_lon))
                if dist > MAX_RADIUS:
                    continue # Uzoq bo'lsa tashlab ketamiz
            
            driver_url = f"{XARITA_LINKI}/index.html?order_id={uid}&driver_id={d_id}&clat={lat}&clon={lon}"
            kb_drv = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", web_app=WebAppInfo(url=driver_url))],
                [InlineKeyboardButton(text="📍 Yandex Xarita", url=f"https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map")]
            ])
            try:
                await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤: {message.from_user.full_name}\n📍 Masofa: {dist:.1f} km" if d_lat else f"🔔 **Yangi buyurtma!**", reply_markup=kb_drv, parse_mode="Markdown")
                drivers_sent += 1
            except: continue

@dp.message(F.text == "🔄 Rolni o'zgartirish")
async def reset_user(message: Message):
    requests.delete(f"{BASE_URL}users/{message.from_user.id}.json")
    await message.answer("Rolingiz o'chirildi. /start bosing.")

async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(watch_all_events())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

