from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
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
import hashlib
import requests
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

# ==================== FLASK APP ====================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_bot_2026")
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

# ==================== DIRECTORIOS ====================
TEMP_DIR = "temp"
UPLOADS_DIR = "static/uploads"

for dir_path in [TEMP_DIR, UPLOADS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

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
    """Extrae el ID de YouTube de una URL"""
    if not url: return None
    # Patrones de YouTube
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]+)',
        r'(?:youtu\.be\/)([\w-]+)',
        r'(?:youtube\.com\/shorts\/)([\w-]+)',
        r'(?:youtube\.com\/embed\/)([\w-]+)',
        r'(?:youtube\.com\/v\/)([\w-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# ==================== FUNCIÓN PARA OBTENER THUMBNAIL ====================
def download_thumbnail(video_id):
    """Descarga el thumbnail de YouTube y lo guarda en uploads/"""
    if not video_id:
        return None
    
    # URLs de thumbnail de YouTube (de mejor a peor calidad)
    thumb_urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/0.jpg",
    ]
    
    for url in thumb_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                thumb_filename = f"thumb_{video_id}_{int(time.time())}.jpg"
                thumb_path = os.path.join(UPLOADS_DIR, thumb_filename)
                with open(thumb_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Thumbnail descargado: {thumb_filename}")
                return thumb_filename, f"/uploads/{thumb_filename}"
        except Exception as e:
            print(f"Error descargando thumbnail: {e}")
            continue
    
    return None, None

# ==================== FUNCIÓN DE SUBIDA ====================
def upload_file(filepath, filename=None):
    """Sube un archivo al servidor y devuelve el enlace"""
    if filename is None:
        filename = os.path.basename(filepath)
    
    # Copiar a uploads
    dest_path = os.path.join(UPLOADS_DIR, filename)
    
    # Si ya existe, agregar número
    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(dest_path):
        new_name = f"{base}_{counter}{ext}"
        dest_path = os.path.join(UPLOADS_DIR, new_name)
        filename = new_name
        counter += 1
    
    shutil.copy2(filepath, dest_path)
    
    # Generar enlace público
    if PUBLIC_URL:
        link = f"{PUBLIC_URL.rstrip('/')}/uploads/{filename}"
    else:
        link = f"http://localhost:5000/uploads/{filename}"
    
    return link, filename

# ==================== SEGURIDAD WEB ====================
@app.before_request
def proteger():
    libres = ["/", "/bot/post", "/webhook", "/logout", "/gato", "/downloader", "/uploads"]
    if request.path.startswith("/static") or request.path.startswith("/uploads"):
        return
    if request.path in libres:
        return
    if not session.get("login"):
        return redirect("/")
    session.modified = True

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOADS_DIR, filename)

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
def panel():
    return render_template("panel.html")

@app.route("/posts")
def posts():
    return render_template("posts.html", posts=load_posts())

@app.route("/store")
def store():
    return render_template("store.html", productos=load_store())

@app.route("/gato")
def gato():
    return render_template("gato.html")

@app.route("/downloader")
def downloader():
    return render_template("downloader.html")

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

# ==================== ESTADOS PARA CONVERSACIONES ====================
UPLOAD_WAITING_FILE = 1
WAITING_YT_LINK = 2
WAITING_YT_NAME = 3

# ==================== MENÚ PRINCIPAL ====================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ No autorizado")
        return
    
    keyboard = [
        [InlineKeyboardButton("📤 Subir Archivo", callback_data="upload_file")],
        [InlineKeyboardButton("📹 Agregar Video YouTube", callback_data="yt_add_start")],
        [InlineKeyboardButton("📋 Ver Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await update.message.reply_text(
        "🤖 **PAPI DEXTER BOT**\n\n"
        "📤 **Sube archivos a tu web**\n"
        "📥 Obtén enlaces directos\n\n"
        f"📁 **Dominio:** {PUBLIC_URL or 'localhost'}\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== SUBIR ARCHIVO ====================
async def upload_file_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="upload_cancel")]]
    
    await query.edit_message_text(
        "📤 **SUBIR ARCHIVO**\n\n"
        "📌 Envía el archivo que quieras subir\n\n"
        "Puedes enviar:\n"
        "• 📁 Archivo cualquiera\n"
        "• 📷 Imagen\n"
        "• 🎬 Video\n"
        "• 📦 ZIP\n\n"
        "📁 Se guardará en tu web:\n"
        f"`{PUBLIC_URL or 'localhost'}/uploads/`\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return UPLOAD_WAITING_FILE

async def receive_file(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
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
    else:
        await update.message.reply_text("❌ Archivo no soportado")
        return UPLOAD_WAITING_FILE
    
    await update.message.reply_text("📥 Procesando archivo...")
    
    try:
        if hasattr(file_obj, 'get_file'):
            file = await file_obj.get_file()
        else:
            file = file_obj
        
        temp_path = os.path.join(TEMP_DIR, file_name)
        await file.download_to_drive(temp_path)
        
        # Subir al servidor
        link, final_name = upload_file(temp_path, file_name)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        size_mb = os.path.getsize(os.path.join(UPLOADS_DIR, final_name)) / (1024 * 1024)
        
        keyboard = [
            [InlineKeyboardButton("🔗 Abrir Enlace", url=link)],
            [InlineKeyboardButton("📤 Subir otro", callback_data="upload_file")],
            [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
        ]
        
        await update.message.reply_text(
            f"✅ **ARCHIVO SUBIDO**\n\n"
            f"📁 **Nombre:** `{final_name}`\n"
            f"📦 **Tamaño:** {size_mb:.2f} MB\n"
            f"🔗 **Enlace:** [Descargar]({link})\n\n"
            f"📌 Guarda este enlace.",
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
    await query.edit_message_text("❌ Subida cancelada", parse_mode="Markdown")
    return ConversationHandler.END

# ==================== YOUTUBE CON THUMBNAIL ====================
async def yt_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    await query.edit_message_text(
        "📹 **AGREGAR VIDEO DE YOUTUBE**\n\n"
        "📌 **PASO 1:** Envía el **link de YouTube**\n\n"
        "Ejemplos:\n"
        "`https://youtu.be/xxxxx`\n"
        "`https://www.youtube.com/watch?v=xxxxx`\n"
        "`https://youtube.com/shorts/xxxxx`\n\n"
        "🖼️ **El thumbnail se descargará automáticamente**\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_YT_LINK

async def yt_receive_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    url = update.message.text.strip()
    video_id = get_video_id(url)
    
    if not video_id:
        await update.message.reply_text(
            "❌ **Link inválido**\n\n"
            "Envía un link válido de YouTube.\n"
            "Ejemplo: `https://youtu.be/xxxxx`",
            parse_mode="Markdown"
        )
        return WAITING_YT_LINK
    
    ctx.user_data['yt_url'] = url
    ctx.user_data['yt_id'] = video_id
    
    # Descargar thumbnail
    await update.message.reply_text(f"🖼️ Descargando thumbnail para `{video_id}`...", parse_mode="Markdown")
    
    thumb_filename, thumb_url = download_thumbnail(video_id)
    ctx.user_data['thumb_filename'] = thumb_filename
    ctx.user_data['thumb_url'] = thumb_url
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    if thumb_url:
        await update.message.reply_photo(
            photo=thumb_url,
            caption=f"✅ **Thumbnail descargado**\n\n"
                    f"📌 **PASO 2:** Envía el **nombre del archivo**\n\n"
                    f"Ejemplo:\n"
                    f"`video_skin`\n\n"
                    f"📁 Se guardará como: `video_skin.unity3d`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚠️ No se pudo descargar el thumbnail\n\n"
            f"📌 **PASO 2:** Envía el **nombre del archivo**\n\n"
            f"Ejemplo:\n"
            f"`video_skin`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    return WAITING_YT_NAME

async def yt_receive_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        await update.message.reply_text("❌ Nombre inválido (mínimo 2 caracteres)")
        return WAITING_YT_NAME
    
    url = ctx.user_data.get('yt_url')
    video_id = ctx.user_data.get('yt_id')
    thumb_filename = ctx.user_data.get('thumb_filename')
    thumb_url = ctx.user_data.get('thumb_url')
    
    # Guardar en posts
    posts = load_posts()
    posts.append({
        "youtube": url,
        "file": name,
        "video_id": video_id,
        "thumbnail": thumb_url,
        "thumb_filename": thumb_filename,
        "created": time.time()
    })
    save_posts(posts)
    
    keyboard = [
        [InlineKeyboardButton("📹 Ver Videos", callback_data="yt_list")],
        [InlineKeyboardButton("📤 Agregar otro", callback_data="yt_add_start")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    message_text = (
        f"✅ **VIDEO AGREGADO**\n\n"
        f"📹 **Link:** {url}\n"
        f"📁 **Archivo:** `{name}`\n"
        f"🖼️ **Thumbnail:** {thumb_url or 'No disponible'}\n\n"
        f"📌 El thumbnail se mostrará en la lista de videos."
    )
    
    if thumb_url:
        await update.message.reply_photo(
            photo=thumb_url,
            caption=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    ctx.user_data.clear()
    return ConversationHandler.END

async def yt_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.edit_message_text("❌ Operación cancelada", parse_mode="Markdown")
    return ConversationHandler.END

async def yt_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos guardados.")
        return
    
    # Mostrar videos con thumbnail
    for i, p in enumerate(posts):
        thumb = p.get('thumbnail')
        name = p.get('file', 'sin nombre')
        url = p.get('youtube', 'sin link')
        
        message = f"📹 **{i}. {name}**\n\n🔗 {url}"
        
        if thumb and os.path.exists(os.path.join('.', thumb.lstrip('/'))):
            try:
                with open(os.path.join('.', thumb.lstrip('/')), 'rb') as f:
                    await query.message.reply_photo(
                        photo=InputFile(f),
                        caption=message,
                        parse_mode="Markdown"
                    )
            except:
                await query.message.reply_text(message, parse_mode="Markdown")
        else:
            await query.message.reply_text(message, parse_mode="Markdown")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    await query.message.reply_text(
        "📋 **FIN DE LA LISTA**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ TIENDA ====================
async def menu_store(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Agregar", callback_data="store_add")],
        [InlineKeyboardButton("📋 Listar", callback_data="store_list")],
        [InlineKeyboardButton("🗑️ Eliminar", callback_data="store_delete")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🛒 **TIENDA**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def store_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📦 **Agregar Producto**\n\n"
        "`/addstore nombre | precio | desc | link`",
        parse_mode="Markdown"
    )

async def store_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 Sin productos.")
        return
    txt = "🛒 **PRODUCTOS:**\n\n"
    for i, p in enumerate(data):
        txt += f"{i}. **{p.get('nombre')}** | ${p.get('precio')}\n"
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def store_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 Sin productos.")
        return
    keyboard = []
    for i, p in enumerate(data):
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {p.get('nombre')[:20]}", callback_data=f"del_store_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_store")])
    await query.edit_message_text("🗑️ **SELECCIONA PRODUCTO:**", reply_markup=InlineKeyboardMarkup(keyboard))

async def store_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        idx = int(query.data.split("_")[2])
        data = load_store()
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            save_store(data)
            await query.edit_message_text(f"✅ Eliminado: `{removed.get('nombre')}`")
        else:
            await query.edit_message_text("❌ Error")
    except:
        await query.edit_message_text("❌ Error")
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    await query.edit_message_text("🗑️ **ELIMINADO**", reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== MENÚ KEYS ====================
async def menu_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar", callback_data="keys_gen")],
        [InlineKeyboardButton("📋 Ver", callback_data="keys_list")],
        [InlineKeyboardButton("🗑️ Eliminar", callback_data="keys_del")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🔑 **KEYS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_gen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔑 `/genkey cantidad`", parse_mode="Markdown")

async def keys_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keys = load_keys()
    if not keys:
        await query.edit_message_text("🔑 Sin keys.")
        return
    txt = "🔑 **KEYS:**\n\n"
    for i, k in enumerate(keys):
        txt += f"{i+1}. `{k}`\n"
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_keys")]]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def keys_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("✅ SI", callback_data="keys_del_confirm")],
        [InlineKeyboardButton("❌ NO", callback_data="menu_keys")]
    ]
    await query.edit_message_text("⚠️ **¿ELIMINAR TODAS?**", reply_markup=InlineKeyboardMarkup(keyboard))

async def keys_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_keys([])
    await query.edit_message_text("🗑️ Keys eliminadas.")

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
    
    txt = f"""📊 **ESTADÍSTICAS**

📹 Videos: {posts}
🛒 Productos: {store}
🔑 Keys: {keys}
⏱️ Uptime: {hours}h {minutes}m

📁 Archivos en: `{PUBLIC_URL or 'localhost'}/uploads/`"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== INFO ====================
async def menu_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    txt = """ℹ️ **PAPI DEXTER BOT**

🤖 Bot de gestión de archivos

📌 **Funciones:**
• 📤 Subir archivos a tu web
• 📹 Agregar videos de YouTube (con thumbnail)
• 🛒 Tienda
• 🔑 Keys

📁 **Tu web:** `{PUBLIC_URL or 'localhost'}`

⚡ Versión 6.0 - Con Thumbnails de YouTube"""
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_main")]]
    await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==================== BACK TO MAIN ====================
async def back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📤 Subir Archivo", callback_data="upload_file")],
        [InlineKeyboardButton("📹 Agregar Video YouTube", callback_data="yt_add_start")],
        [InlineKeyboardButton("📋 Ver Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await query.edit_message_text(
        "🤖 **PAPI DEXTER BOT**\n\n"
        "📤 **Sube archivos a tu web**\n"
        "📥 Obtén enlaces directos\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== COMANDOS ====================
async def yt_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    if len(ctx.args) < 2:
        await update.message.reply_text("Uso: /yt link nombre")
        return
    try:
        posts = load_posts()
        video_id = get_video_id(ctx.args[0])
        thumb_filename, thumb_url = download_thumbnail(video_id) if video_id else (None, None)
        posts.append({
            "youtube": ctx.args[0],
            "file": ctx.args[1],
            "video_id": video_id,
            "thumbnail": thumb_url,
            "thumb_filename": thumb_filename,
            "created": time.time()
        })
        save_posts(posts)
        await update.message.reply_text(f"✅ Video: {ctx.args[1]}")
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
        data = load_store()
        data.append({"nombre": partes[0].strip(), "precio": partes[1].strip(), "descripcion": partes[2].strip(), "link": partes[3].strip(), "imagen": None})
        save_store(data)
        await update.message.reply_text(f"✅ Producto: {partes[0].strip()}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def genkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    try:
        n = int(ctx.args[0]) if ctx.args else 1
        if n > 100:
            await update.message.reply_text("❌ Máximo 100")
            return
        keys = load_keys()
        nuevas = [gen_key() for _ in range(n)]
        keys.extend(nuevas)
        save_keys(keys)
        txt = "\n".join(nuevas)
        file = io.BytesIO(txt.encode())
        file.name = "keys.txt"
        await update.message.reply_document(InputFile(file, filename="keys.txt"))
    except:
        await update.message.reply_text("❌ Uso: /genkey cantidad")

# ==================== CONFIGURACIÓN DEL BOT ====================
def setup_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    
    bot.add_handler(CommandHandler("start", start_cmd))
    bot.add_handler(CommandHandler("yt", yt_cmd))
    bot.add_handler(CommandHandler("addstore", addstore_cmd))
    bot.add_handler(CommandHandler("genkey", genkey_cmd))
    
    # Subir Archivo
    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_file_start, pattern="^upload_file$")],
        states={
            UPLOAD_WAITING_FILE: [
                MessageHandler(filters.Document.ALL, receive_file),
                MessageHandler(filters.PHOTO, receive_file),
                MessageHandler(filters.VIDEO, receive_file),
            ],
        },
        fallbacks=[CallbackQueryHandler(upload_cancel, pattern="^upload_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(upload_conv)
    
    # YouTube con Thumbnail
    yt_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(yt_add_start, pattern="^yt_add_start$")],
        states={
            WAITING_YT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_link)],
            WAITING_YT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_name)],
        },
        fallbacks=[CallbackQueryHandler(yt_cancel, pattern="^yt_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(yt_conv)
    
    # Callbacks
    bot.add_handler(CallbackQueryHandler(yt_list, pattern="^yt_list$"))
    bot.add_handler(CallbackQueryHandler(menu_store, pattern="^menu_store$"))
    bot.add_handler(CallbackQueryHandler(menu_keys, pattern="^menu_keys$"))
    bot.add_handler(CallbackQueryHandler(menu_stats, pattern="^menu_stats$"))
    bot.add_handler(CallbackQueryHandler(menu_info, pattern="^menu_info$"))
    bot.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    
    bot.add_handler(CallbackQueryHandler(store_add, pattern="^store_add$"))
    bot.add_handler(CallbackQueryHandler(store_list, pattern="^store_list$"))
    bot.add_handler(CallbackQueryHandler(store_delete, pattern="^store_delete$"))
    bot.add_handler(CallbackQueryHandler(store_delete_confirm, pattern="^del_store_"))
    
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
    print(f"✅ Bot iniciado - Archivos en: {PUBLIC_URL or 'localhost'}/uploads/")
    await bot.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)