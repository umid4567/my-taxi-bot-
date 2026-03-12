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

# --- 1. KUZATUVCHI (MIJOZGA XABAR YUBORISH) ---
async def watch_all_events():
    """Mijozga haydovchi qabul qilgani haqida xabar yuborish tizimi"""
    print("✅ Kuzatuv tizimi ishga tushdi...")
    while True:
        try:
            # Firebase'dan buyurtmalarni olish (keshlanmasligi uchun vaqt qo'shildi)
            res = requests.get(f"{BASE_URL}orders.json").json()
            
            if res:
                for uid, data in res.items():
                    # Status 'accepted' bo'lsa va hali bildirishnoma bormagan bo'lsa
                    if data.get("status") == "accepted" and data.get("client_notified") is not True:
                        
                        kuzatish_url = f"{XARITA_LINKI}passenger.html?order_id={uid}"
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                        ])
                        
                        text = "🚕 **Xushxabar!** Buyurtmangiz qabul qilindi.\n\nHaydovchi yo'lga chiqdi. Pastdagi tugma orqali uni xaritada kuzatishingiz mumkin."
                        
                        try:
                            # Mijozga xabar yuborish
                            await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="Markdown")
                            
                            # Qayta yubormaslik uchun bazada belgilab qo'yish
                            requests.patch(f"{BASE_URL}orders/{uid}.json", json={"client_notified": True})
                            print(f"📧 Mijozga ({uid}) bildirishnoma yuborildi.")
                        except Exception as send_err:
                            print(f"❌ Xabar yuborishda xato ({uid}): {send_err}")
                            
        except Exception as e:
            print(f"⚠️ Kuzatuvda xatolik: {e}")
            
        await asyncio.sleep(5) # Telegram qotmasligi uchun ideal vaqt

# --- 2. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()

    if user_data and user_data.get("role") == "driver":
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚖 Yangi buyurtmalarni kutish", 
                            web_app=WebAppInfo(url=f"{XARITA_LINKI}driver_db.html?driver_id={uid}"))],
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
    full_name = message.from_user.full_name
    
    # Yangi buyurtma yaratish (barcha xabarlarni reset qilib)
    order_data = {
        "lat": lat, 
        "lon": lon, 
        "name": full_name, 
        "status": "waiting",
        "client_notified": False, # Xabarlarni yangilash
        "msg_sent": False
    }
    requests.put(f"{BASE_URL}orders/{uid}.json", json=order_data)
    
    kb_cancel = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Buyurtmani bekor qilish", callback_data=f"cancel_{uid}")]
    ])
    await message.answer("🚕 Buyurtma yuborildi. Haydovchi kutilmoqda...", reply_markup=kb_cancel)
    
    # Haydovchilarga bildirish yuborish
    all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    for d_id, d_data in all_users.items():
        if d_data.get("role") == "driver":
            driver_url = f"{XARITA_LINKI}index.html?order_id={uid}&clat={lat}&clon={lon}"
            kb_drv = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", web_app=WebAppInfo(url=driver_url))]
            ])
            try:
                await bot.send_message(d_id, f"🔔 **Yangi buyurtma!**\n👤 Mijoz: {full_name}", reply_markup=kb_drv, parse_mode="Markdown")
            except: continue

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    requests.delete(f"{BASE_URL}orders/{c_id}.json")
    await callback.message.edit_text("❌ Buyurtma bekor qilindi.")
    await callback.answer()

@dp.callback_query(F.data.startswith("set_role_"))
async def set_role(callback: types.CallbackQuery):
    role = callback.data.split("_")[2]
    requests.put(f"{BASE_URL}users/{callback.from_user.id}.json", json={"role": role, "name": callback.from_user.full_name})
    await callback.message.answer("Saqlandi! /start bosing.")
    await callback.answer()

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
