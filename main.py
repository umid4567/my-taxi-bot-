import os
import asyncio
import requests
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot" 

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

# --- 1. KUZATUVCHI ---
async def watch_all_events():
    while True:
        try:
            r = requests.get(f"{BASE_URL}orders.json")
            orders = r.json()
            if orders:
                for order_id, data in orders.items():
                    # Status 'accepted' bo'lganda yo'lovchiga kuzatuv tugmasini yuboramiz
                    if data.get("status") == "accepted" and data.get("client_notified") is not True:
                        kuzatish_url = f"{XARITA_LINKI}/passenger.html?order_id={order_id}"
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                        ])
                        text = "🚕 **Buyurtmangiz qabul qilindi!**\n\nHaydovchi yo'lga chiqdi. Pastdagi tugma orqali uni kuzating."
                        try:
                            await bot.send_message(chat_id=str(order_id), text=text, reply_markup=kb, parse_mode="Markdown")
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"client_notified": True})
                        except:
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"client_notified": True})
        except Exception as e:
            print(f"⚠️ Tizimda xatolik: {e}")
        await asyncio.sleep(3)

# --- 2. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()
    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Buyurtmalarni kutish", web_app=WebAppInfo(url=f"{XARITA_LINKI}/driver_db.html?driver_id={uid}"))],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer(f"Salom haydovchi {user_data.get('name')}!", reply_markup=kb)
    elif user_data and user_data.get("role") == "client":
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

# --- 3. BUYURTMA BERISH ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude
    order_data = {"lat": lat, "lon": lon, "name": message.from_user.full_name, "status": "waiting", "client_notified": False}
    requests.put(f"{BASE_URL}orders/{uid}.json", json=order_data)
    
    kb_cancel = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{uid}")]])
    await message.answer("🚕 Buyurtma yuborildi. Haydovchi kutilmoqda...", reply_markup=kb_cancel)
    
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    for d_id, d_data in all_users.items():
        if d_data.get("role") == "driver":
            driver_url = f"{XARITA_LINKI}/index.html?order_id={uid}&clat={lat}&clon={lon}"
            kb_drv = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", web_app=WebAppInfo(url=driver_url))],
                [InlineKeyboardButton(text="📍 Yandex Xarita", url=f"https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map")]
            ])
            try:
                await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤: {message.from_user.full_name}", reply_markup=kb_drv, parse_mode="Markdown")
            except: continue

@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    requests.put(f"{BASE_URL}users/{callback.from_user.id}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.answer("Saqlandi! /start bosing.")

async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(watch_all_events())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
