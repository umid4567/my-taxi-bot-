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
    print("🚀 Kuzatuv tizimi ishga tushdi...")
    while True:
        try:
            r = requests.get(f"{BASE_URL}orders.json")
            orders = r.json()
            
            if orders:
                for order_id, data in orders.items():
                    current_status = data.get("status")
                    
                    if current_status in ["accepted", "coming"] and data.get("client_notified") is not True:
                        print(f"🔔 Mijoz {order_id} uchun kuzatuv tugmasi tayyorlanmoqda...")
                        
                        kuzatish_url = f"{XARITA_LINKI}/passenger.html?order_id={order_id}"
                        
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))]
                        ])
                        
                        text = "🚕 **Haydovchi buyurtmani qabul qildi!**\n\nPastdagi tugma orqali uni xaritada jonli kuzatib turing."
                        
                        try:
                            await bot.send_message(chat_id=order_id, text=text, reply_markup=kb, parse_mode="Markdown")
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"client_notified": True})
                            print(f"✅ Mijozga xabar yuborildi: {order_id}")
                        except Exception as e:
                            print(f"❌ Telegram xabar yubora olmadi: {e}")
                            requests.patch(f"{BASE_URL}orders/{order_id}.json", json={"client_notified": True})
            
        except Exception as e:
            print(f"⚠️ Firebase xatosi: {e}")
            
        await asyncio.sleep(3)


# --- 2. START KOMANDASI ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    try:
        user_data = requests.get(f"{BASE_URL}users/{uid}.json").json()
    except:
        user_data = None

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
    
    # 1. Buyurtmani bazaga yozish (Mijozga tugma yuborilganini belgilaymiz)
    order_data = {
        "lat": lat, 
        "lon": lon, 
        "name": message.from_user.full_name, 
        "status": "waiting", 
        "client_notified": True 
    }
    requests.put(f"{BASE_URL}orders/{uid}.json", json=order_data)
    
    # 2. YO'LOVCHI UCHUN TUGMALAR (Kuzatish va Bekor qilish)
    kuzatish_url = f"{XARITA_LINKI}/passenger.html?order_id={uid}"
    
    kb_client = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚕 Haydovchini kuzatish", web_app=WebAppInfo(url=kuzatish_url))],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{uid}")]
    ])
    
    await message.answer(
        "🚕 **Buyurtma yuborildi. Haydovchi kutilmoqda...**\n\nPastdagi tugma orqali haydovchi qabul qilganidan so'ng uni kuzatishingiz mumkin.", 
        reply_markup=kb_client,
        parse_mode="Markdown"
    )
    
    # 3. HAYDOVCHILARGA BUYURTMANI YUBORISH
    try:
        all_users = requests.get(f"{BASE_URL}users.json").json() or {}
    except:
        all_users = {}

    for d_id, d_data in all_users.items():
        if d_data.get("role") == "driver":
            # Haydovchi uchun taksimetr va xarita havolasi
            driver_url = f"{XARITA_LINKI}/index.html?order_id={uid}&clat={lat}&clon={lon}"
            
            kb_drv = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Qabul qilish", web_app=WebAppInfo(url=driver_url))],
                [InlineKeyboardButton(text="📍 Yandex Xarita", url=f"https://yandex.uz/maps/?pt={lon},{lat}&z=16&l=map")]
            ])
            
            try:
                await bot.send_message(
                    d_id, 
                    f"🔔 **Yangi buyurtma!**\n👤: {message.from_user.full_name}", 
                    reply_markup=kb_drv, 
                    parse_mode="Markdown"
                )
            except: 
                continue


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

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    asyncio.create_task(start_web_server())
    asyncio.create_task(watch_all_events())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi!")
