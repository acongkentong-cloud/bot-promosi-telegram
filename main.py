import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Import data dari file data.py
from data import VALID_USER_ID, VALID_PASSWORD, GROUPS

# Token Bot dari @BotFather (Diset via Environment Variable Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# State Conversation
LOGIN_USER, LOGIN_PASS, MAIN_MENU, WAIT_PROMO_INPUT, CONFIRM_PROMO = range(5)

# --- HANDLER START & AUTHENTICATION ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cek status login
    if context.user_data.get("authenticated"):
        return await show_main_menu(update, context)

    await update.message.reply_text("Silakan masukkan **User ID** Anda:")
    return LOGIN_USER

async def process_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_user = update.message.text.strip()
    if input_user == VALID_USER_ID:
        context.user_data["temp_user"] = input_user
        await update.message.reply_text("User ID cocok!\nSekarang masukkan **Password**:")
        return LOGIN_PASS
    else:
        await update.message.reply_text("❌ User ID salah. Silakan kirim /start untuk coba lagi.")
        return ConversationHandler.END

async def process_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    input_pass = update.message.text.strip()
    if input_pass == VALID_PASSWORD:
        keyboard = [[InlineKeyboardButton("🔑 Login Sekarang", callback_data="do_login")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Password sesuai! Klik tombol di bawah untuk masuk:", reply_markup=reply_markup)
        return LOGIN_PASS
    else:
        await update.message.reply_text("❌ Password salah. Silakan kirim /start untuk coba lagi.")
        return ConversationHandler.END

async def do_login_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["authenticated"] = True
    await query.edit_message_text("✅ **Login Berhasil!**")
    return await show_main_menu(update, context)

# --- MAIN MENU & ALUR PROMOSI ---

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📢 Sebar Promosi", callback_data="menu_sebar")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "Selamat datang di Panel Promosi Group!\nSilakan pilih menu di bawah:"
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return MAIN_MENU

async def menu_sebar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Silakan kirimkan **teks promosi** beserta **gambar** (bila ada) dalam **1 pesan sekaligus** (gunakan fitur Caption/Keterangan pada gambar).\n\n"
        "Jika *hanya teks*, kirim teks saja."
    )
    return WAIT_PROMO_INPUT

async def receive_promo_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    caption = msg.caption or msg.text or ""
    photo_file_id = msg.photo[-1].file_id if msg.photo else None

    if not caption and not photo_file_id:
        await msg.reply_text("Pesan kosong! Kirimkan teks atau gambar dengan teks.")
        return WAIT_PROMO_INPUT

    # Simpan materi di context
    context.user_data["promo_text"] = caption
    context.user_data["promo_photo"] = photo_file_id

    # Konfirmasi ulang materi
    keyboard = [
        [InlineKeyboardButton("🚀 GAS KIRIM", callback_data="broadcast_gas")],
        [InlineKeyboardButton("❌ Batal / Reset", callback_data="broadcast_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.reply_text("🔍 **Konfirmasi Pesan Promosi:**\nApakah materi berikut sudah sesuai?")
    
    if photo_file_id:
        await msg.reply_photo(photo=photo_file_id, caption=caption, reply_markup=reply_markup)
    else:
        await msg.reply_text(text=caption, reply_markup=reply_markup)

    return CONFIRM_PROMO

async def broadcast_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "broadcast_cancel":
        await query.edit_message_text("Promosi dibatalkan.")
        return await show_main_menu(update, context)

    # Tindakan "GAS KIRIM"
    await query.edit_message_text("⏳ **Mengirimkan promosi ke semua group...**")
    
    text = context.user_data.get("promo_text")
    photo = context.user_data.get("promo_photo")

    success = 0
    failed = 0

    for group_id in GROUPS:
        try:
            if photo:
                await context.bot.send_photo(chat_id=group_id, photo=photo, caption=text)
            else:
                await context.bot.send_message(chat_id=group_id, text=text)
            success += 1
        except Exception as e:
            failed += 1
            logging.error(f"Gagal kirim ke group {group_id}: {e}")

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"📊 **Hasil Broadcast:**\n\n✅ Berhasil: {success} Group\n❌ Gagal: {failed} Group"
    )

    return await show_main_menu(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sesi dihentikan. Kirim /start untuk mulai lagi.")
    return ConversationHandler.END

# --- MAIN RUNNER ---

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tidak ditemukan di Environment Variable!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOGIN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user)],
            LOGIN_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_pass),
                CallbackQueryHandler(do_login_callback, pattern="^do_login$")
            ],
            MAIN_MENU: [CallbackQueryHandler(menu_sebar_callback, pattern="^menu_sebar$")],
            WAIT_PROMO_INPUT: [MessageHandler(filters.TEXT | filters.PHOTO, receive_promo_content)],
            CONFIRM_PROMO: [
                CallbackQueryHandler(broadcast_action, pattern="^broadcast_gas$"),
                CallbackQueryHandler(broadcast_action, pattern="^broadcast_cancel$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
