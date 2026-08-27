from flask import Flask, render_template, request, redirect, session, jsonify
import os
import json
import aiohttp
import asyncio
import random
import string
import io
import time
import re
import threading
import shutil
from datetime import timedelta
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# ==================== MEGA API ====================
from mega import Mega

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_mega_bot_2026")
app.permanent_session_lifetime = timedelta(minutes=30)

# ==================== CONFIGURACIÓN ====================
USUARIO = "PAPI"
PASSWORD = "DEXTER"
MASTER_KEY = os.environ.get("MASTER_KEY", "CHINITA")

DB_FILE = "database.json"
KEYS_FILE = "keys.json"
STORE_FILE = "store.json"

TOKEN = os.environ.get("BOT_TOKEN")
PUBLIC_URL = os.environ.get("PUBLIC_URL")
ADMIN_ID = 6841201622

# ==================== CONFIGURACIÓN MEGA ====================
MEGA_EMAIL = os.environ.get("MEGA_EMAIL", "tu_email@ejemplo.com")
MEGA_PASSWORD = os.environ.get("MEGA_PASSWORD", "tu_contraseña_mega")

TEMP_DIR = "temp"
UPLOADS_DIR = "uploads"

for dir_path in [TEMP_DIR, UPLOADS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

API_URL = f"{PUBLIC_URL.rstrip('/')}/bot/post" if PUBLIC_URL else "http://localhost:5000/bot/post"
START_TIME = time.time()

# ==================== FUNCIONES JSON ====================
def load_json(file):
    if not os.path.exists(file): return []
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)

def load_posts(): return load_json(DB_FILE)
def save_posts(d): save_json(DB_FILE, d)
def load_keys(): return load_json(KEYS_FILE)
def save_keys(d): save_json(KEYS_FILE, d)
def load_store(): return load_json(STORE_FILE)
def save_store(d): save_json(STORE_FILE, d)

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def get_video_id(url):
    if not url: return None
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url: return url.split("youtu.be/")[1].split("?")[0]
    return None

# ==================== MEGA FUNCTIONS ====================
class MegaUploader:
    def __init__(self):
        self.mega = None
        self.connected = False
        self._connect()
    
    def _connect(self):
        try:
            if MEGA_EMAIL and MEGA_PASSWORD:
                self.mega = Mega()
                self.mega.login(MEGA_EMAIL, MEGA_PASSWORD)
                self.connected = True
                print("✅ Conectado a MEGA")
            else:
                print("⚠️ Credenciales MEGA no configuradas")
        except Exception as e:
            print(f"❌ Error conectando a MEGA: {e}")
            self.connected = False
    
    def upload_file(self, filepath, filename=None):
        """Sube un archivo a MEGA y devuelve el enlace"""
        if not self.connected:
            self._connect()
            if not self.connected:
                return None, "❌ No se pudo conectar a MEGA"
        
        try:
            if filename is None:
                filename = os.path.basename(filepath)
            
            print(f"📤 Subiendo {filename} a MEGA...")
            
            # Subir archivo
            result = self.mega.upload(filepath, filename)
            
            # Obtener enlace
            link = self.mega.get_upload_link(result)
            
            print(f"✅ Archivo subido: {link}")
            return link, None
        except Exception as e:
            print(f"❌ Error subiendo archivo: {e}")
            return None, f"❌ Error subiendo archivo: {e}"
    
    def upload_bytes(self, data, filename):
        """Sube datos en bytes a MEGA y devuelve el enlace"""
        if not self.connected:
            self._connect()
            if not self.connected:
                return None, "❌ No se pudo conectar a MEGA"
        
        try:
            # Guardar temporalmente
            temp_path = os.path.join(TEMP_DIR, filename)
            with open(temp_path, 'wb') as f:
                f.write(data)
            
            # Subir a MEGA
            result = self.mega.upload(temp_path, filename)
            link = self.mega.get_upload_link(result)
            
            # Eliminar temporal
            os.remove(temp_path)
            
            return link, None
        except Exception as e:
            return None, f"❌ Error subiendo archivo: {e}"

# ==================== SEGURIDAD WEB ====================
@app.before_request
def proteger():
    libres = ["/", "/bot/post", "/webhook", "/logout", "/gato", "/downloader"]
    if request.path.startswith("/static"): return
    if request.path in libres: return
    if not session.get("login"): return redirect("/")
    session.modified = True

# ==================== RUTAS WEB ====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("user")
        password = request.form.get("pass")
        key = request.form.get("key")
        keys = load_keys()
        if user == USUARIO and password == PASSWORD:
            if key == MASTER_KEY or key in keys:
                if key in keys and key != MASTER_KEY:
                    keys.remove(key); save_keys(keys)
                session.permanent = True; session["login"] = True
                return redirect("/panel")
        return render_template("index.html", error="❌ Login incorrecto")
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect("/")

@app.route("/panel")
def panel(): return render_template("panel.html")

@app.route("/posts")
def posts(): return render_template("posts.html", posts=load_posts())

@app.route("/store")
def store(): return render_template("store.html", productos=load_store())

@app.route("/gato")
def gato(): return render_template("gato.html")

@app.route("/downloader")
def downloader(): return render_template("downloader.html")

@app.route("/bot/post", methods=["POST"])
def bot_post():
    try:
        data = request.json
        if not data: return jsonify({"error": "No data"}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== BOT ====================
def is_admin(update):
    try: return update.effective_user.id == ADMIN_ID
    except: return False

# ==================== MENÚ PRINCIPAL ====================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ No autorizado")
        return
    
    keyboard = [
        [InlineKeyboardButton("📤 Subir Archivo a MEGA", callback_data="mega_upload")],
        [InlineKeyboardButton("📋 Ver Mis Archivos", callback_data="mega_list")],
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await update.message.reply_text(
        "🤖 **PAPI DEXTER BOT**\n\n"
        "📤 **Sube archivos a MEGA**\n"
        "📥 Obtén enlaces de descarga directos\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MEGA UPLOAD ====================
UPLOAD_WAITING_FILE = 1

async def mega_upload_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="upload_cancel")]]
    
    await query.edit_message_text(
        "📤 **SUBIR ARCHIVO A MEGA**\n\n"
        "📌 **PASO 1:** Envía el archivo que quieras subir\n\n"
        "Puedes enviar:\n"
        "• 📁 Archivo cualquiera\n"
        "• 📷 Imagen\n"
        "• 🎬 Video\n"
        "• 📦 ZIP\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return UPLOAD_WAITING_FILE

async def mega_receive_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    # Verificar si es documento, foto o video
    file_obj = None
    file_name = None
    
    if update.message.document:
        file_obj = update.message.document
        file_name = file_obj.file_name
    elif update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        file_name = f"foto_{int(time.time())}.jpg"
    elif update.message.video:
        file_obj = update.message.video
        file_name = f"video_{int(time.time())}.mp4"
    elif update.message.audio:
        file_obj = update.message.audio
        file_name = f"audio_{int(time.time())}.mp3"
    else:
        await update.message.reply_text(
            "❌ **Archivo no soportado**\n\n"
            "Envía un documento, foto, video o audio.\n"
            "Usa /start para cancelar.",
            parse_mode="Markdown"
        )
        return UPLOAD_WAITING_FILE
    
    # Descargar archivo
    await update.message.reply_text("📥 Descargando archivo...")
    
    try:
        # Obtener el archivo
        if hasattr(file_obj, 'get_file'):
            file = await file_obj.get_file()
        else:
            file = file_obj
        
        # Guardar en temp
        temp_path = os.path.join(TEMP_DIR, file_name)
        await file.download_to_drive(temp_path)
        
        await update.message.reply_text(f"📤 Subiendo `{file_name}` a MEGA...", parse_mode="Markdown")
        
        # Subir a MEGA
        uploader = MegaUploader()
        link, error = uploader.upload_file(temp_path, file_name)
        
        # Eliminar temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if error:
            await update.message.reply_text(f"❌ {error}")
            return ConversationHandler.END
        
        # Enviar resultado
        keyboard = [
            [InlineKeyboardButton("🔗 Abrir Enlace", url=link)],
            [InlineKeyboardButton("📤 Subir otro", callback_data="mega_upload")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        
        # Obtener tamaño
        size_kb = os.path.getsize(temp_path) / 1024 if os.path.exists(temp_path) else 0
        
        await update.message.reply_text(
            f"✅ **ARCHIVO SUBIDO CON ÉXITO**\n\n"
            f"📁 **Nombre:** `{file_name}`\n"
            f"📦 **Tamaño:** {size_kb:.1f} KB\n"
            f"🔗 **Enlace:** [Descargar]({link})\n\n"
            f"📌 El enlace es válido mientras tengas la cuenta MEGA activa.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        ctx.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        ctx.user_data.clear()
        return ConversationHandler.END

async def upload_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Subida cancelada**\n\n"
        "Usa /start para volver al menú principal.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ==================== MEGA LIST ====================
async def mega_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📋 **MIS ARCHIVOS EN MEGA**\n\n"
        "📌 Para ver tus archivos, usa el cliente de MEGA:\n"
        "• Web: https://mega.nz\n"
        "• App: MEGA en Play Store\n\n"
        "📤 **Sube archivos** desde el bot usando\n"
        "la opción 'Subir Archivo a MEGA'",
        parse_mode="Markdown"
    )

# ==================== MENÚ YOUTUBE ====================
async def menu_yt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Agregar Video", callback_data="yt_add")],
        [InlineKeyboardButton("📋 Listar Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🗑️ Eliminar Video", callback_data="yt_delete")],
        [InlineKeyboardButton("🧹 Limpiar Todo", callback_data="yt_clear")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "📹 **GESTIÓN DE VIDEOS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ TIENDA ====================
async def menu_store(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Producto", callback_data="store_add")],
        [InlineKeyboardButton("📋 Listar Productos", callback_data="store_list")],
        [InlineKeyboardButton("🗑️ Eliminar Producto", callback_data="store_delete")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🛒 **GESTIÓN DE TIENDA**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ KEYS ====================
async def menu_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar Keys", callback_data="keys_gen")],
        [InlineKeyboardButton("📋 Ver Keys", callback_data="keys_list")],
        [InlineKeyboardButton("🗑️ Eliminar Keys", callback_data="keys_del")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🔑 **GESTIÓN DE KEYS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== ESTADÍSTICAS ====================
async def menu_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = len(load_posts())
    store = len(load_store())
    keys = len(load_keys())
    uptime_sec = int(time.time() - START_TIME)
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    seconds = uptime_sec % 60
    
    txt = f"""📊 **ESTADÍSTICAS**

📹 Videos: {posts}
🛒 Productos: {store}
🔑 Keys: {keys}
⏱️ Uptime: {hours}h {minutes}m {seconds}s

📤 MEGA: Conectado ✅
🤖 Bot activo ✅"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== INFO ====================
async def menu_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    txt = """ℹ️ **PAPI DEXTER BOT**

🤖 Bot de gestión con MEGA

📌 **Funciones:**
• 📤 Subir archivos a MEGA
• 📹 Gestión de videos YouTube
• 🛒 Tienda de productos
• 🔑 Generación de keys
• 📊 Estadísticas en tiempo real

📦 **MEGA:** Subida automática
🔗 Enlaces directos de descarga

👤 Admin: PAPI DEXTER

⚡ Versión 4.0 - Con MEGA API"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== BACK TO MAIN ====================
async def back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📤 Subir Archivo a MEGA", callback_data="mega_upload")],
        [InlineKeyboardButton("📋 Ver Mis Archivos", callback_data="mega_list")],
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await query.edit_message_text(
        "🤖 **PAPI DEXTER BOT**\n\n"
        "📤 **Sube archivos a MEGA**\n"
        "📥 Obtén enlaces de descarga directos\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== COMANDOS DE TEXTO ====================
async def yt_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if len(ctx.args) < 2:
        await update.message.reply_text("Uso: /yt link archivo")
        return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(API_URL, json={"youtube": ctx.args[0], "file": ctx.args[1]})
        await update.message.reply_text(f"✅ Video publicado: {ctx.args[1]}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def addstore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        texto = " ".join(ctx.args)
        partes = texto.split("|")
        if len(partes) < 4:
            await update.message.reply_text("Uso: /addstore nombre | precio | desc | link")
            return
        nombre, precio, desc, link = partes[0].strip(), partes[1].strip(), partes[2].strip(), partes[3].strip()
        data = load_store()
        data.append({"nombre": nombre, "precio": precio, "descripcion": desc, "link": link, "imagen": None})
        save_store(data)
        await update.message.reply_text(f"✅ Producto creado: {nombre}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def genkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        n = int(ctx.args[0]) if ctx.args else 1
        if n > 100:
            await update.message.reply_text("❌ Máximo 100 keys por vez")
            return
        keys = load_keys()
        nuevas = [gen_key() for _ in range(n)]
        keys.extend(nuevas)
        save_keys(keys)
        txt = "\n".join(nuevas)
        file = io.BytesIO(txt.encode())
        file.name = "keys.txt"
        await update.message.reply_document(InputFile(file, filename="keys.txt"))
    except ValueError:
        await update.message.reply_text("❌ Uso: /genkey cantidad")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ==================== CONFIGURACIÓN DEL BOT ====================
def setup_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Comandos
    bot.add_handler(CommandHandler("start", start_cmd))
    bot.add_handler(CommandHandler("yt", yt_cmd))
    bot.add_handler(CommandHandler("addstore", addstore_cmd))
    bot.add_handler(CommandHandler("genkey", genkey_cmd))
    
    # ===== CONVERSACIÓN: MEGA UPLOAD =====
    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mega_upload_start, pattern="^mega_upload$")],
        states={
            UPLOAD_WAITING_FILE: [
                MessageHandler(filters.Document.ALL, mega_receive_file),
                MessageHandler(filters.PHOTO, mega_receive_file),
                MessageHandler(filters.VIDEO, mega_receive_file),
                MessageHandler(filters.AUDIO, mega_receive_file),
            ],
        },
        fallbacks=[CallbackQueryHandler(upload_cancel, pattern="^upload_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(upload_conv)
    
    # Callbacks - Menú Principal
    bot.add_handler(CallbackQueryHandler(mega_list, pattern="^mega_list$"))
    bot.add_handler(CallbackQueryHandler(menu_yt, pattern="^menu_yt$"))
    bot.add_handler(CallbackQueryHandler(menu_store, pattern="^menu_store$"))
    bot.add_handler(CallbackQueryHandler(menu_keys, pattern="^menu_keys$"))
    bot.add_handler(CallbackQueryHandler(menu_stats, pattern="^menu_stats$"))
    bot.add_handler(CallbackQueryHandler(menu_info, pattern="^menu_info$"))
    bot.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    
    # Callbacks - YouTube
    bot.add_handler(CallbackQueryHandler(yt_add, pattern="^yt_add$"))
    bot.add_handler(CallbackQueryHandler(yt_list, pattern="^yt_list$"))
    bot.add_handler(CallbackQueryHandler(yt_delete, pattern="^yt_delete$"))
    bot.add_handler(CallbackQueryHandler(yt_clear, pattern="^yt_clear$"))
    bot.add_handler(CallbackQueryHandler(yt_delete_confirm, pattern="^del_yt_"))
    bot.add_handler(CallbackQueryHandler(yt_clear_confirm, pattern="^yt_clear_confirm$"))
    
    # Callbacks - Store
    bot.add_handler(CallbackQueryHandler(store_add, pattern="^store_add$"))
    bot.add_handler(CallbackQueryHandler(store_list, pattern="^store_list$"))
    bot.add_handler(CallbackQueryHandler(store_delete, pattern="^store_delete$"))
    bot.add_handler(CallbackQueryHandler(store_delete_confirm, pattern="^del_store_"))
    
    # Callbacks - Keys
    bot.add_handler(CallbackQueryHandler(keys_gen, pattern="^keys_gen$"))
    bot.add_handler(CallbackQueryHandler(keys_list, pattern="^keys_list$"))
    bot.add_handler(CallbackQueryHandler(keys_del, pattern="^keys_del$"))
    bot.add_handler(CallbackQueryHandler(keys_del_confirm, pattern="^keys_del_confirm$"))
    
    return bot

# ==================== MAIN ====================
async def run_bot():
    bot = setup_bot()
    await bot.initialize()
    await bot.start()
    print("✅ Bot iniciado con MEGA API")
    await bot.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)