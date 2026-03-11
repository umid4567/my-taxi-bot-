import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# --- 1. SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN") 
BASE_URL = "https://umut-taxi-default-rtdb.europe-west1.firebasedatabase.app/"
# Web App manzillaringiz (GitHub Pages linki)
XARITA_LINKI = "https://umid4567.github.io/my-taxi-bot/index.html" 
PASSENGER_LINKI = "https://umid4567.github.io/my-taxi-bot/passenger.html"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 2. FIREBASE BILAN ASINXRON ISHLASH ---
async def firebase_get(path):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}{path}.json") as resp:
            return await resp.json()

async def firebase_put(path, data):
    async with aiohttp.ClientSession() as session:
        async with session.put(f"{BASE_URL}{path}.json", json=data) as resp:
            return await resp.json()

async def firebase_delete(path):
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{BASE_URL}{path}.json") as resp:
            return await resp.json()

# --- 3. RENDER UCHUN PORT VA STATUS ---
async def handle(request):
    return web.Response(text="AXI TAXI Bot is running!")

async def on_startup(app):
    # Bot polling-ni fonda ishga tushiramiz
    asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    print("🚀 Bot va Server birga zavod bo'ldi!")

# --- 4. BOT KOMANDALARI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = await firebase_get(f"users/{uid}")

    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish")],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer(f"Xush kelibsiz, Umid aka!", reply_markup=kb)
    elif user_data and user_data.get("role") == "client":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚕 Taksi chaqirish", request_location=True)],
            [KeyboardButton(text="🔄 Rolni o'zgartirish")]
        ], resize_keyboard=True)
        await message.answer("Xush kelibsiz! Qayerga boramiz?", reply_markup=kb)
    else:
        kb_start = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚖 Men yo'lovchiman", callback_data="set_role_client")],
            [InlineKeyboardButton(text="🚕 Men haydovchiman", callback_data="set_role_driver")]
        ])
        await message.answer("Xush kelibsiz! Ro'yxatdan o'ting:", reply_markup=kb_start)

@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    uid = callback.from_user.id
    await firebase_put(f"users/{uid}", {"role": role, "name": callback.from_user.full_name})
    await callback.message.answer(f"✅ Saqlandi! /start bosing.")
    await callback.answer()

@dp.message(F.text == "🔄 Rolni o'zgartirish")
async def reset_role(message: Message):
    uid = message.from_user.id
    await firebase_delete(f"users/{uid}")
    await message.answer("Rolingiz o'chirildi. /start bosing.")

# --- 5. BUYURTMA VA QABUL QILISH ---
@dp.message(F.location)
async def handle_location(message: Message):
    uid = message.from_user.id
    lat, lon = message.location.latitude, message.location.longitude
    await firebase_put(f"orders/{uid}", {"lat": lat, "lon": lon, "name": message.from_user.full_name})
    await message.answer("🚕 Buyurtma yuborildi. Haydovchi qidirilmoqda...")
    
    users = await firebase_get("users") or {}
    for d_id, data in users.items():
        if data.get("role") == "driver":
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept_{uid}_{lat}_{lon}")]
            ])
            try: await bot.send_message(d_id, f"🔔 Yangi buyurtma!\n👤: {message.from_user.full_name}", reply_markup=kb)
            except: continue

@dp.callback_query(F.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    _, c_id, c_lat, c_lon = callback.data.split("_")
    await firebase_delete(f"orders/{c_id}")
    
    order_id = f"{c_id}_{int(asyncio.get_event_loop().time())}"
    
    # Haydovchiga Web App (Taksimetr)
    driver_url = f"{XARITA_LINKI}?order_id={order_id}&clat={c_lat}&clon={c_lon}"
    kb_d = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚕 Taksimetrni ochish", web_app=WebAppInfo(url=driver_url))]
    ])
    await callback.message.edit_text("✅ Safar boshlanishiga tayyor!", reply_markup=kb_d)
    
    # Yo'lovchiga kuzatuv xaritasi
    pass_url = f"{PASSENGER_LINKI}?order_id={order_id}"
    kb_p = Inline

