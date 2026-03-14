import os
import asyncio
import requests
import math
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
# GitHub Pages manzilingizni oxiridagi '/' belgisiz yozing
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot" 
MAX_RADIUS = 5.0 # km

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYA: Masofani hisoblash ---
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 1. ROL TANLASH ---
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
        f"Siz **{role}** rolingizni tanladingiz.\nBog'lanish uchun telefon raqamingizni yuboring:", 
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
    await message.answer("✅ Rahmat! Endi /start bosing.", reply_markup=ReplyKeyboardRemove())

# --- RENDER SERVER ---
async def handle(request):
    return web.Response(text="Axi Taxi Bot ishlayapti!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- KUZATUVCHI (Mijozga bildirishnoma) ---
async def watch_all_events():
    while True:
        try:
            r = requests.get(f"{BASE_URL}orders.json")
            orders = r.json()
            if orders:
                for order_id, data in orders.items():
                    # Agar buyurtma qabul qilinsa va mijozga hali xabar bormagan bo'lsa
                    if data.get("status") == "accepted" and data.get("driver_notified_client") is not True:
                        kuzatish_url = f"{XARITA_LINKI}/passenger.html?order_id={order_id}"
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                        ])
                        text = "🚕 **Haydovchi buyurtmani qabul qildi!**\n\nUni xaritada jonli kuzatishingiz mumkin."
                        try:
                            await bot.send_message(chat_id=order_id, text=text, reply_markup=kb, parse_mode="Markdown")
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"driver_notified_client": True})
                        except: pass
        except: pass
        await asyncio.sleep(4)

# --- START KOMANDASI (Yandex Style Web App bilan) ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()
    
    if user_data and user_data.get("phone"):
        if user_data.get("role") == "driver":
            # Haydovchi uchun menyu
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="🚖 Buyurtmalarni kutish", web_app=WebAppInfo(url=f"{XARITA_LINKI}/index.html?driver_id={uid}"))],
                [KeyboardButton(text="🔄 Rolni o'zgartirish")]
            ], resize_keyboard=True)
            await message.answer(f"Xush kelibsiz, haydovchi {user_data.get('name')}!", reply_markup=kb)
        else:
            # Yo'lovchi uchun menyu (order.html ulandi)
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="🚕 Taksi chaqirish", web_app=WebAppInfo(url=f"{XARITA_LINKI}/order.html"))],
                [KeyboardButton(text="🔄 Rolni o'zgartirish")]
            ], resize_keyboard=True)
            await message.answer("Taksi chaqirish uchun tugmani bosing:", reply_markup=kb)
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Avval rolingizni tanlang:", reply_markup=kb_start)

# --- WEB APP'DAN KELGAN MA'LUMOTNI QABUL QILISH ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    data = message.web_app_data.data
    uid = message.from_user.id
    
    if data.startswith("order_placed"):
        await message.answer("✅ Buyurtmangiz qabul qilindi! Haydovchi qidirilmoqda...")
        
        # Firebase'dan yangi buyurtma ma'lumotlarini olamiz
        order = requests.get(f"{BASE_URL}orders/{uid}.json").json()
        if not order: return

        # Haydovchilarga yuborish
        all_users = requests.get(f"{BASE_URL}users.json").json() or {}
        for d_id, d_data in all_users.items():
            if d_data.get("role") == "driver":
                driver_url = f"{XARITA_LINKI}/index.html?order_id={uid}&driver_id={d_id}&clat={order['lat']}&clon={order['lon']}"
                kb_drv = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Qabul qilish", web_app=WebAppInfo(url=driver_url))],
                    [InlineKeyboardButton(text="📍 Yandex Xarita", url=f"https://yandex.uz/maps/?pt={order['lon']},{order['lat']}&z=16&l=map")]
                ])
                try:
                    await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤: {order.get('name')}\n💰 Narxi: {order.get('price')} so'm", reply_markup=kb_drv, parse_mode="Markdown")
                except: continue

# --- ROLNI O'ZGARTIRISH ---
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
