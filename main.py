import os
import asyncio
import requests
from aiohttp import web # SHU YERDA YANGI QISMI
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/" 
DRIVER_APP = "https://umid4567.github.io/my-taxi-bot/driver_db.html"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- RENDER UCHUN SOXTA SERVER (PORT MUAMMOSINI HAL QILISH) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render o'zi beradigan portni oladi (odatda 10000)
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")

# --- 1. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    if user_data and user_data.get("role") == "driver":
        # HAYDOVCHI UCHUN TUGMALAR
        kb = ReplyKeyboardMarkup(keyboard=[
            # BU TUGMA ENDI WEB APP PANELNI OCHADI
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish", 
                            web_app=WebAppInfo(url=f"{XARITA_LINKI}driver_db.html?driver_id={uid}"))],
            [KeyboardButton(text="💰 Mening balansim")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, haydovchi {user_data.get('name')}! Panelni ochish uchun pastdagi tugmani bosing.", reply_markup=kb)

    elif user_data and user_data.get("role") == "client":
        # YO'LOVCHI UCHUN TUGMALAR
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
            [KeyboardButton(text="ℹ️ Ma'lumot")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Taksi kerak bo'lsa tugmani bosing.", reply_markup=kb)
    
    else:
        # ROL TANLANMAGAN BO'LSA
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Rolingizni tanlang:", reply_markup=kb_start)


# --- 2. ROLNI BOSHQARISH ---
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

# --- 3. BUYURTMA BERISH (YO'LOVCHI) ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat = round(message.location.latitude, 5)
    lon = round(message.location.longitude, 5)
    
    requests.put(f"{BASE_URL}orders/{uid}.json", json={
        "lat": lat, "lon": lon, "name": message.from_user.full_name
    })
    
    await message.answer("🚕 Buyurtmangiz yuborildi. Iltimos kuting...")
    
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    for d_id, data in all_users.items():
        if data.get("role") == "driver":
            kb_h = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{uid}_{lat}_{lon}")]
            ])
            try:
                await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤 Yo'lovchi: {message.from_user.full_name}", reply_markup=kb_h)
            except: continue

# --- 4. QABUL QILISH (HAYDOVCHI) ---
@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    data = callback.data.split("_")
    # data[1] - bu yo'lovchining IDsi (c_id)
    # data[2], data[3] - mijozning turgan joyi
    c_id, c_lat, c_lon = data[1], data[2], data[3]
    
    # Bazadan buyurtmani o'chirib, "safar" boshlanganini belgilaymiz
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    
    # HAYDOVCHI UCHUN LINK (Mijozga borish marshruti bilan)
    driver_link = f"{XARITA_LINKI}index.html?order_id={c_id}&clat={c_lat}&clon={c_lon}"
    kb_driver = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Marshrutni ko'rish", web_app=WebAppInfo(url=driver_link))]
    ])
    await callback.message.edit_text("✅ Buyurtma qabul qilindi!", reply_markup=kb_driver)

    # YO'LOVCHI UCHUN LINK (Haydovchini kuzatish uchun)
    # E'tibor bering: fayl nomi passenger.html bo'lishi shart!
    passenger_link = f"{XARITA_LINKI}passenger.html?order_id={c_id}"
    kb_passenger = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=passenger_link))]
    ])
    
    try:
        await bot.send_message(c_id, "🚕 Haydovchi buyurtmani qabul qildi!", reply_markup=kb_passenger)
    except Exception as e:
        print(f"Yo'lovchiga xabar yuborishda xato: {e}")
        
    await callback.answer()


# --- 5. WEB APP'DAN MA'LUMOT ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    result = message.web_app_data.data
    if result.startswith("arrived_"):
        await message.answer("✅ Ajoyib! Mijozga yetib kelganingiz haqida xabar berildi. Yo'lingiz bexatar bo'lsin! 🏁")

# --- ASOSIY MAIN FUNKSIYASI ---
async def main():
    # Render kutayotgan soxta serverni ishga tushiramiz
    asyncio.create_task(start_web_server())
    # Botni ishga tushiramiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
