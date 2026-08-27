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

# ==================== ESTADOS PARA CONVERSACIONES ====================
UPLOAD_WAITING_FILE = 1
WAITING_YT_LINK = 2
WAITING_YT_DOWNLOAD = 3
WAITING_STORE_NAME = 10
WAITING_STORE_PRICE = 11
WAITING_STORE_DESC = 12
WAITING_STORE_LINK = 13
WAITING_KEYS_COUNT = 20

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
    if "youtube.com/shorts/" in url:
        return url.split("youtube.com/shorts/")[1].split("?")[0]
    return None

# ==================== FUNCIÓN PARA OBTENER THUMBNAIL ====================
def get_thumbnail_url(video_id):
    """Obtiene la URL del thumbnail de YouTube sin descargarlo"""
    if not video_id:
        return None
    
    thumb_urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/0.jpg",
    ]
    
    for url in thumb_urls:
        try:
            response = requests.head(url, timeout=3)
            if response.status_code == 200:
                return url
        except:
            continue
    
    return None

# ==================== FUNCIÓN DE SUBIDA ====================
def upload_file(filepath, filename=None):
    if filename is None:
        filename = os.path.basename(filepath)
    dest_path = os.path.join(UPLOADS_DIR, filename)
    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(dest_path):
        new_name = f"{base}_{counter}{ext}"
        dest_path = os.path.join(UPLOADS_DIR, new_name)
        filename = new_name
        counter += 1
    shutil.copy2(filepath, dest_path)
    if PUBLIC_URL:
        link = f"{PUBLIC_URL.rstrip('/')}/uploads/{filename}"
    else:
        link = f"http://localhost:5000/uploads/{filename}"
    return link, filename

# ==================== FUNCIÓN PARA LISTAR ARCHIVOS ====================
def get_file_list(folder):
    files = []
    if os.path.exists(folder):
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path):
                files.append(f)
    return sorted(files)

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

# ==================== MENÚ PRINCIPAL ====================
async def show_main_menu(update_or_query, ctx):
    """Función para mostrar el menú principal desde cualquier lugar"""
    web_url = PUBLIC_URL or "https://dexter-modz-sk.onrender.com"
    
    keyboard = [
        [InlineKeyboardButton("📤 Subir Archivo", callback_data="upload_file")],
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("🌐 Mi Web", url=web_url)],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    message = f"🤖 **PAPI DEXTER BOT**\n\n🌐 **Web:** {web_url}\n\n📤 **Sube archivos a tu web**\n📹 **Agrega videos de YouTube**\n\nSelecciona una opción:"
    
    if hasattr(update_or_query, 'message'):
        await update_or_query.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update_or_query.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ No autorizado")
        return
    
    await show_main_menu(update, ctx)

# ==================== SUBIR ARCHIVO CON OPCIÓN DE BORRAR ====================
async def upload_file_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    
    files = get_file_list(UPLOADS_DIR)
    
    keyboard = []
    
    if files:
        for i, f in enumerate(files[:10]):
            path = os.path.join(UPLOADS_DIR, f)
            size_kb = os.path.getsize(path) / 1024
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ {i+1}. {f[:20]} ({size_kb:.1f}KB)",
                    callback_data=f"del_before_{i}"
                )
            ])
        
        total_size = sum(os.path.getsize(os.path.join(UPLOADS_DIR, f)) for f in files)
        total_mb = total_size / (1024 * 1024)
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Borrar Todos ({len(files)} archivos, {total_mb:.1f}MB)",
                callback_data="del_before_all"
            )
        ])
        
        keyboard.append([InlineKeyboardButton("─" * 30, callback_data="none")])
    
    keyboard.append([
        InlineKeyboardButton("📤 Subir Archivo", callback_data="upload_start")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")
    ])
    
    message = "📤 **SUBIR ARCHIVO**\n\n"
    
    if files:
        message += f"📁 **Archivos existentes:** {len(files)}\n"
        message += f"📦 **Espacio usado:** {total_mb:.2f} MB\n"
        message += f"💾 **Límite Render:** ~1 GB\n\n"
        message += "🗑️ **Borra archivos viejos** antes de subir nuevos:\n\n"
    else:
        message += "📌 **No hay archivos guardados.**\n\n"
        message += "📌 Envía el archivo que quieras subir\n\n"
        message += "Puedes enviar:\n"
        message += "• 📁 Archivo cualquiera\n"
        message += "• 📷 Imagen\n"
        message += "• 🎬 Video\n"
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return UPLOAD_WAITING_FILE

# ==================== BORRAR ARCHIVO ANTES DE SUBIR ====================
async def delete_before_upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        idx = int(query.data.split("_")[2])
        files = get_file_list(UPLOADS_DIR)
        
        if 0 <= idx < len(files):
            filename = files[idx]
            filepath = os.path.join(UPLOADS_DIR, filename)
            
            if os.path.exists(filepath):
                os.remove(filepath)
                await query.answer(f"✅ Eliminado: {filename}", show_alert=True)
        
        await upload_file_start(update, ctx)
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {e}")

async def delete_before_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI, borrar todo", callback_data="del_all_before_confirm")],
        [InlineKeyboardButton("❌ NO, cancelar", callback_data="upload_file")]
    ]
    
    files = get_file_list(UPLOADS_DIR)
    total_size = sum(os.path.getsize(os.path.join(UPLOADS_DIR, f)) for f in files)
    total_mb = total_size / (1024 * 1024)
    
    await query.edit_message_text(
        f"⚠️ **¿BORRAR TODOS LOS ARCHIVOS?**\n\n"
        f"📁 **Archivos:** {len(files)}\n"
        f"📦 **Tamaño:** {total_mb:.2f} MB\n\n"
        f"Esta acción **no se puede deshacer**.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def delete_all_before_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    files = get_file_list(UPLOADS_DIR)
    deleted = 0
    
    for f in files:
        filepath = os.path.join(UPLOADS_DIR, f)
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted += 1
    
    await query.answer(f"✅ {deleted} archivos eliminados", show_alert=True)
    await upload_file_start(update, ctx)

# ==================== INICIAR SUBIDA ====================
async def upload_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="upload_cancel")]]
    
    await query.edit_message_text(
        "📤 **ENVÍA EL ARCHIVO**\n\n"
        "📌 Envía el archivo que quieras subir\n\n"
        "Puedes enviar:\n"
        "• 📁 Archivo cualquiera\n"
        "• 📷 Imagen\n"
        "• 🎬 Video\n\n"
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
        
        link, final_name = upload_file(temp_path, file_name)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        size_mb = os.path.getsize(os.path.join(UPLOADS_DIR, final_name)) / (1024 * 1024)
        
        await update.message.reply_text(
            f"✅ **ARCHIVO SUBIDO**\n\n"
            f"📁 **Nombre:** `{final_name}`\n"
            f"📦 **Tamaño:** {size_mb:.2f} MB\n"
            f"🔗 **Enlace:** [Descargar]({link})\n\n"
            f"📌 Guarda este enlace.",
            parse_mode="Markdown"
        )
        
        ctx.user_data.clear()
        await asyncio.sleep(1)
        await show_main_menu(update, ctx)
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        ctx.user_data.clear()
        await asyncio.sleep(1)
        await show_main_menu(update, ctx)
        return ConversationHandler.END

async def upload_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.clear()
    await query.edit_message_text("❌ Subida cancelada", parse_mode="Markdown")
    await asyncio.sleep(1)
    await show_main_menu(query, ctx)
    return ConversationHandler.END

# ==================== AGREGAR VIDEO (SOLO LINK YT + LINK DESCARGA) ====================
async def yt_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    await query.edit_message_text(
        "📹 **AGREGAR VIDEO**\n\n"
        "📌 **PASO 1:** Envía el **link de YouTube**\n\n"
        "Ejemplos:\n"
        "`https://youtu.be/xxxxx`\n"
        "`https://www.youtube.com/watch?v=xxxxx`\n"
        "`https://youtube.com/shorts/xxxxx`\n\n"
        "📌 **PASO 2:** Luego envía el **link de descarga**\n\n"
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
    
    # Obtener thumbnail sin descargar
    thumb_url = get_thumbnail_url(video_id)
    ctx.user_data['thumb_url'] = thumb_url
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    await update.message.reply_text(
        f"✅ **Link de YouTube guardado**\n\n"
        f"📌 **PASO 2:** Envía el **link de descarga**\n\n"
        f"Puede ser de:\n"
        f"• MediaFire\n"
        f"• Mega\n"
        f"• Google Drive\n"
        f"• Cualquier otro servicio\n\n"
        f"Ejemplo:\n"
        f"`https://www.mediafire.com/file/xxxxx`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_YT_DOWNLOAD

async def yt_receive_download(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    download_link = update.message.text.strip()
    
    # Validar que sea un link válido
    if not download_link.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ **Link inválido**\n\n"
            "Debe comenzar con `http://` o `https://`\n"
            "Ejemplo: `https://www.mediafire.com/file/xxxxx`",
            parse_mode="Markdown"
        )
        return WAITING_YT_DOWNLOAD
    
    ctx.user_data['download_link'] = download_link
    
    # Guardar en posts
    posts = load_posts()
    posts.append({
        "youtube": ctx.user_data.get('yt_url'),
        "video_id": ctx.user_data.get('yt_id'),
        "thumbnail": ctx.user_data.get('thumb_url'),
        "download": download_link,
        "created": time.time()
    })
    save_posts(posts)
    
    keyboard = [
        [InlineKeyboardButton("📹 Agregar otro", callback_data="yt_add_start")],
        [InlineKeyboardButton("📋 Listar Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
    ]
    
    message = f"""✅ **VIDEO AGREGADO**

📹 **YouTube:** {ctx.user_data.get('yt_url')}
📥 **Descarga:** {download_link}"""
    
    await update.message.reply_text(
        message,
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
    await asyncio.sleep(1)
    await show_main_menu(query, ctx)
    return ConversationHandler.END

# ==================== LISTAR VIDEOS ====================
async def yt_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos.")
        await asyncio.sleep(1.5)
        await menu_yt(update, ctx)
        return
    
    for i, p in enumerate(posts):
        thumb = p.get('thumbnail')
        youtube = p.get('youtube', 'sin link')
        download = p.get('download', 'sin link')
        video_id = p.get('video_id', '')
        
        message = f"📹 **Video {i+1}**\n\n"
        message += f"📹 **YouTube:** {youtube}\n"
        message += f"📥 **Descarga:** {download}\n"
        
        if thumb:
            try:
                await query.message.reply_photo(
                    photo=thumb,
                    caption=message,
                    parse_mode="Markdown"
                )
            except:
                await query.message.reply_text(message, parse_mode="Markdown")
        else:
            await query.message.reply_text(message, parse_mode="Markdown")
    
    await asyncio.sleep(1)
    await menu_yt(update, ctx)

# ==================== ELIMINAR VIDEO ====================
async def yt_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos.")
        await asyncio.sleep(1.5)
        await menu_yt(update, ctx)
        return
    
    keyboard = []
    for i, p in enumerate(posts):
        youtube = p.get('youtube', 'sin link')[:25]
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {youtube}...", callback_data=f"del_yt_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA VIDEO:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_delete_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        idx = int(query.data.split("_")[2])
        posts = load_posts()
        if 0 <= idx < len(posts):
            removed = posts.pop(idx)
            save_posts(posts)
            await query.edit_message_text(f"✅ Video eliminado")
        else:
            await query.edit_message_text("❌ Error")
    except:
        await query.edit_message_text("❌ Error")
    
    await asyncio.sleep(1)
    await menu_yt(update, ctx)

# ==================== LIMPIAR VIDEOS ====================
async def yt_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI", callback_data="yt_clear_confirm")],
        [InlineKeyboardButton("❌ NO", callback_data="menu_yt")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODOS?**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_clear_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_posts([])
    await query.edit_message_text("🧹 Todos eliminados.")
    await asyncio.sleep(1)
    await menu_yt(update, ctx)

# ==================== MENÚ YOUTUBE ====================
async def menu_yt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Agregar Video", callback_data="yt_add_start")],
        [InlineKeyboardButton("📋 Listar Videos", callback_data="yt_list")],
        [InlineKeyboardButton("🗑️ Eliminar Video", callback_data="yt_delete")],
        [InlineKeyboardButton("🧹 Limpiar Todo", callback_data="yt_clear")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
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
        [InlineKeyboardButton("➕ Agregar Producto", callback_data="store_add_start")],
        [InlineKeyboardButton("📋 Listar Productos", callback_data="store_list")],
        [InlineKeyboardButton("🗑️ Eliminar Producto", callback_data="store_delete")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🛒 **TIENDA**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def store_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="store_cancel")]]
    
    await query.edit_message_text(
        "📦 **AGREGAR PRODUCTO**\n\n"
        "📌 **PASO 1:** Envía el **nombre del producto**\n\n"
        "Ejemplo:\n"
        "`Skin XP Legendaria`\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_STORE_NAME

async def store_receive_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        await update.message.reply_text(
            "❌ **Nombre inválido**\n\n"
            "El nombre debe tener al menos 2 caracteres.\n"
            "Ejemplo: `Skin XP Legendaria`",
            parse_mode="Markdown"
        )
        return WAITING_STORE_NAME
    
    ctx.user_data['store_name'] = name
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="store_cancel")]]
    
    await update.message.reply_text(
        f"✅ **Nombre:** `{name}`\n\n"
        "📌 **PASO 2:** Envía el **precio**\n\n"
        "Ejemplo:\n"
        "`10.99`\n"
        "`25`\n"
        "`Gratis`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_STORE_PRICE

async def store_receive_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    price = update.message.text.strip()
    
    if not price:
        await update.message.reply_text(
            "❌ **Precio inválido**\n\n"
            "Ejemplo: `10.99` o `Gratis`",
            parse_mode="Markdown"
        )
        return WAITING_STORE_PRICE
    
    ctx.user_data['store_price'] = price
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="store_cancel")]]
    
    await update.message.reply_text(
        f"✅ **Precio:** `{price}`\n\n"
        "📌 **PASO 3:** Envía la **descripción**\n\n"
        "Ejemplo:\n"
        "`Skin exclusiva con efectos especiales`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_STORE_DESC

async def store_receive_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    desc = update.message.text.strip()
    
    if not desc or len(desc) < 3:
        await update.message.reply_text(
            "❌ **Descripción inválida**\n\n"
            "La descripción debe tener al menos 3 caracteres.",
            parse_mode="Markdown"
        )
        return WAITING_STORE_DESC
    
    ctx.user_data['store_desc'] = desc
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="store_cancel")]]
    
    await update.message.reply_text(
        f"✅ **Descripción:** `{desc[:50]}...`\n\n"
        "📌 **PASO 4:** Envía el **link del producto**\n\n"
        "Ejemplo:\n"
        "`https://mega.nz/file/xxxxx`\n"
        "`https://drive.google.com/file/xxxxx`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_STORE_LINK

async def store_receive_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    link = update.message.text.strip()
    
    if not link or not link.startswith(('http://', 'https://')):
        await update.message.reply_text(
            "❌ **Link inválido**\n\n"
            "Debe comenzar con `http://` o `https://`",
            parse_mode="Markdown"
        )
        return WAITING_STORE_LINK
    
    data = load_store()
    data.append({
        "nombre": ctx.user_data.get('store_name'),
        "precio": ctx.user_data.get('store_price'),
        "descripcion": ctx.user_data.get('store_desc'),
        "link": link,
        "imagen": None
    })
    save_store(data)
    
    keyboard = [
        [InlineKeyboardButton("➕ Agregar otro", callback_data="store_add_start")],
        [InlineKeyboardButton("📋 Listar Productos", callback_data="store_list")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
    ]
    
    await update.message.reply_text(
        f"✅ **PRODUCTO CREADO**\n\n"
        f"📦 **Nombre:** `{ctx.user_data.get('store_name')}`\n"
        f"💰 **Precio:** `{ctx.user_data.get('store_price')}`\n"
        f"📄 **Descripción:** {ctx.user_data.get('store_desc')}\n"
        f"🔗 **Link:** {link}\n\n"
        f"📸 Puedes enviar una imagen para el producto.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    ctx.user_data.clear()
    return ConversationHandler.END

async def store_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Operación cancelada**\n\n"
        "Usa /menu para volver al menú principal.",
        parse_mode="Markdown"
    )
    
    await asyncio.sleep(1)
    await show_main_menu(query, ctx)
    return ConversationHandler.END

# ==================== LISTAR PRODUCTOS ====================
async def store_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 Sin productos.")
        await asyncio.sleep(1.5)
        await menu_store(update, ctx)
        return
    
    txt = "🛒 **PRODUCTOS:**\n\n"
    for i, p in enumerate(data):
        txt += f"{i}. **{p.get('nombre')}** | ${p.get('precio')}\n"
    
    await query.edit_message_text(txt, parse_mode="Markdown")
    await asyncio.sleep(2)
    await menu_store(update, ctx)

# ==================== ELIMINAR PRODUCTO ====================
async def store_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 Sin productos.")
        await asyncio.sleep(1.5)
        await menu_store(update, ctx)
        return
    
    keyboard = []
    for i, p in enumerate(data):
        nombre = p.get('nombre', f'producto_{i}')[:20]
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {nombre}", callback_data=f"del_store_{i}")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_store")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA PRODUCTO:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

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
    
    await asyncio.sleep(1)
    await menu_store(update, ctx)

# ==================== MENÚ KEYS ====================
async def menu_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar Keys", callback_data="keys_gen_start")],
        [InlineKeyboardButton("📋 Ver Keys", callback_data="keys_list")],
        [InlineKeyboardButton("🗑️ Eliminar Keys", callback_data="keys_del")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🔑 **KEYS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_gen_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="keys_cancel")]]
    
    await query.edit_message_text(
        "🔑 **GENERAR KEYS**\n\n"
        "📌 Envía la **cantidad de keys** que deseas generar\n\n"
        "Ejemplos:\n"
        "`5`\n"
        "`10`\n"
        "`100`\n"
        "`5000` (máximo)\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_KEYS_COUNT

async def keys_receive_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    try:
        n = int(update.message.text.strip())
    except:
        await update.message.reply_text(
            "❌ **Cantidad inválida**\n\n"
            "Envía un número válido.\n"
            "Ejemplo: `5`",
            parse_mode="Markdown"
        )
        return WAITING_KEYS_COUNT
    
    if n < 1:
        await update.message.reply_text(
            "❌ **Cantidad inválida**\n\n"
            "La cantidad debe ser mayor a 0.",
            parse_mode="Markdown"
        )
        return WAITING_KEYS_COUNT
    
    if n > 5000:
        await update.message.reply_text(
            f"❌ **Máximo 5000 keys**\n\n"
            f"Intentaste generar {n} keys.\n"
            f"El límite máximo es 5000.",
            parse_mode="Markdown"
        )
        return WAITING_KEYS_COUNT
    
    keys = load_keys()
    nuevas = [gen_key() for _ in range(n)]
    keys.extend(nuevas)
    save_keys(keys)
    
    txt = "\n".join(nuevas)
    file = io.BytesIO(txt.encode())
    file.name = "keys.txt"
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar más", callback_data="keys_gen_start")],
        [InlineKeyboardButton("📋 Ver Keys", callback_data="keys_list")],
        [InlineKeyboardButton("🔙 Menú Principal", callback_data="back_main")]
    ]
    
    await update.message.reply_document(
        InputFile(file, filename="keys.txt"),
        caption=f"✅ **{n} KEYS GENERADAS**\n\n"
                f"📁 Archivo adjunto con todas las keys.\n"
                f"📌 Máximo permitido: 5000 keys.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    ctx.user_data.clear()
    return ConversationHandler.END

async def keys_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Operación cancelada**\n\n"
        "Usa /menu para volver al menú principal.",
        parse_mode="Markdown"
    )
    
    await asyncio.sleep(1)
    await show_main_menu(query, ctx)
    return ConversationHandler.END

# ==================== LISTAR KEYS ====================
async def keys_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keys = load_keys()
    if not keys:
        await query.edit_message_text("🔑 Sin keys.")
        await asyncio.sleep(1.5)
        await menu_keys(update, ctx)
        return
    
    txt = "🔑 **KEYS:**\n\n"
    for i, k in enumerate(keys):
        txt += f"{i+1}. `{k}`\n"
    
    await query.edit_message_text(txt, parse_mode="Markdown")
    await asyncio.sleep(2)
    await menu_keys(update, ctx)

# ==================== ELIMINAR KEYS ====================
async def keys_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI", callback_data="keys_del_confirm")],
        [InlineKeyboardButton("❌ NO", callback_data="menu_keys")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODAS?**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_keys([])
    await query.edit_message_text("🗑️ Keys eliminadas.")
    await asyncio.sleep(1)
    await menu_keys(update, ctx)

# ==================== ESTADÍSTICAS ====================
async def menu_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = len(load_posts())
    store = len(load_store())
    keys = len(load_keys())
    files = get_file_list(UPLOADS_DIR)
    total_size = sum(os.path.getsize(os.path.join(UPLOADS_DIR, f)) for f in files)
    total_mb = total_size / (1024 * 1024)
    
    uptime_sec = int(time.time() - START_TIME)
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    
    web_url = PUBLIC_URL or "https://dexter-modz-sk.onrender.com"
    
    txt = f"""📊 **ESTADÍSTICAS**

📹 Videos: {posts}
🛒 Productos: {store}
🔑 Keys: {keys}

📁 **Archivos subidos:** {len(files)}
📦 **Espacio usado:** {total_mb:.2f} MB
💾 **Límite Render:** ~1 GB

🌐 **Web:** {web_url}

⏱️ Uptime: {hours}h {minutes}m"""
    
    await query.edit_message_text(txt, parse_mode="Markdown")
    await asyncio.sleep(3)
    await show_main_menu(query, ctx)

# ==================== INFO ====================
async def menu_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    web_url = PUBLIC_URL or "https://dexter-modz-sk.onrender.com"
    
    txt = f"""ℹ️ **PAPI DEXTER BOT**

🤖 Bot de gestión de archivos

📌 **Funciones:**
• 📤 Subir archivos (con opción de borrar)
• 📹 Gestión de videos (thumbnail automático + link descarga)
• 🛒 Tienda
• 🔑 Keys (hasta 5000)

🌐 **Web:** {web_url}

⚡ Versión 7.0 - Sin comandos, solo conversación"""
    
    await query.edit_message_text(txt, parse_mode="Markdown")
    await asyncio.sleep(3)
    await show_main_menu(query, ctx)

# ==================== BACK TO MAIN ====================
async def back_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(query, ctx)

# ==================== COMANDOS ====================
async def addstore_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "📦 **Agregar Producto**\n\n"
        "Usa el botón **➕ Agregar Producto** en el menú Tienda.",
        parse_mode="Markdown"
    )

async def genkey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text(
        "🔑 **Generar Keys**\n\n"
        "Usa el botón **🔑 Generar Keys** en el menú Keys.",
        parse_mode="Markdown"
    )

# ==================== CONFIGURACIÓN DEL BOT ====================
def setup_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    
    bot.add_handler(CommandHandler("start", start_cmd))
    bot.add_handler(CommandHandler("addstore", addstore_cmd))
    bot.add_handler(CommandHandler("genkey", genkey_cmd))
    
    # ===== SUBIR ARCHIVO CON OPCIÓN DE BORRAR =====
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
    
    # ===== BORRAR ANTES DE SUBIR =====
    bot.add_handler(CallbackQueryHandler(delete_before_upload, pattern="^del_before_"))
    bot.add_handler(CallbackQueryHandler(delete_before_all, pattern="^del_before_all$"))
    bot.add_handler(CallbackQueryHandler(delete_all_before_confirm, pattern="^del_all_before_confirm$"))
    bot.add_handler(CallbackQueryHandler(upload_start, pattern="^upload_start$"))
    
    # ===== AGREGAR VIDEO (CONVERSACIÓN) =====
    yt_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(yt_add_start, pattern="^yt_add_start$")],
        states={
            WAITING_YT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_link)],
            WAITING_YT_DOWNLOAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_download)],
        },
        fallbacks=[CallbackQueryHandler(yt_cancel, pattern="^yt_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(yt_conv)
    
    # ===== AGREGAR PRODUCTO (CONVERSACIÓN) =====
    store_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(store_add_start, pattern="^store_add_start$")],
        states={
            WAITING_STORE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_name)],
            WAITING_STORE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_price)],
            WAITING_STORE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_desc)],
            WAITING_STORE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_link)],
        },
        fallbacks=[CallbackQueryHandler(store_cancel, pattern="^store_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(store_conv)
    
    # ===== GENERAR KEYS (CONVERSACIÓN) =====
    keys_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(keys_gen_start, pattern="^keys_gen_start$")],
        states={
            WAITING_KEYS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, keys_receive_count)],
        },
        fallbacks=[CallbackQueryHandler(keys_cancel, pattern="^keys_cancel$")],
        allow_reentry=True
    )
    bot.add_handler(keys_conv)
    
    # ===== CALLBACKS =====
    bot.add_handler(CallbackQueryHandler(menu_yt, pattern="^menu_yt$"))
    bot.add_handler(CallbackQueryHandler(menu_store, pattern="^menu_store$"))
    bot.add_handler(CallbackQueryHandler(menu_keys, pattern="^menu_keys$"))
    bot.add_handler(CallbackQueryHandler(menu_stats, pattern="^menu_stats$"))
    bot.add_handler(CallbackQueryHandler(menu_info, pattern="^menu_info$"))
    bot.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    
    bot.add_handler(CallbackQueryHandler(yt_list, pattern="^yt_list$"))
    bot.add_handler(CallbackQueryHandler(yt_delete, pattern="^yt_delete$"))
    bot.add_handler(CallbackQueryHandler(yt_clear, pattern="^yt_clear$"))
    bot.add_handler(CallbackQueryHandler(yt_delete_confirm, pattern="^del_yt_"))
    bot.add_handler(CallbackQueryHandler(yt_clear_confirm, pattern="^yt_clear_confirm$"))
    
    bot.add_handler(CallbackQueryHandler(store_list, pattern="^store_list$"))
    bot.add_handler(CallbackQueryHandler(store_delete, pattern="^store_delete$"))
    bot.add_handler(CallbackQueryHandler(store_delete_confirm, pattern="^del_store_"))
    
    bot.add_handler(CallbackQueryHandler(keys_list, pattern="^keys_list$"))
    bot.add_handler(CallbackQueryHandler(keys_del, pattern="^keys_del$"))
    bot.add_handler(CallbackQueryHandler(keys_del_confirm, pattern="^keys_del_confirm$"))
    
    return bot

# ==================== MAIN ====================
async def run_bot():
    bot = setup_bot()
    await bot.initialize()
    await bot.start()
    print(f"✅ Bot iniciado - Web: {PUBLIC_URL or 'https://dexter-modz-sk.onrender.com'}")
    await bot.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)