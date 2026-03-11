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
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish")],
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
    if len(data) < 4:
        await callback.answer("⚠️ Ma'lumot yetarli emas!", show_alert=True)
        return

    c_id, c_lat, c_lon = data[1], data[2], data[3]
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    
    marshrut_link = f"{XARITA_LINKI}?clat={c_lat}&clon={c_lon}"
    kb_app = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Marshrutni ko'rish", web_app=WebAppInfo(url=marshrut_link))]
    ])
    
    await callback.message.edit_text("✅ Buyurtma qabul qilindi!", reply_markup=kb_app)
    await bot.send_message(c_id, "🚕 Haydovchi buyurtmani qabul qildi va yo'lga chiqdi!")
    await callback.answer()

# --- 5. WEB APP'DAN MA'LUMOT QABUL QILISH (YANGILANGAN) ---
@dp.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    result = message.web_app_data.data
    
    # 1. Haydovchi manzilga yetib borganda
    if result.startswith("arrived_"):
        await message.answer("🏁 Siz manzilga yetib keldingiz. Mijoz chiqishi bilan 'Safarni boshlash' tugmasini bosing.")
    
    # 2. Safar boshlanganda
    elif result.startswith("trip_started_"):
        await message.answer("🚀 Safar boshlandi! Taksimetr ishga tushdi. Yo'lingiz bexatar bo'lsin!")

    # 3. Safar yakunlanganda (Aniq summa bilan)
    elif result.startswith("finish_"):
        summa = result.split("_")[1]
        await message.answer(f"✅ Safar yakunlandi!\n💰 Jami summa: {summa} so'm.\n\nBaraka toping, Umid aka! Yangi buyurtmalarni kutishingiz mumkin.")
        
        # Bu yerda summani bazaga (Firebase) yozib qo'yish ham mumkin
        # Haydovchining kunlik ishlagan pulini hisoblash uchun


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
