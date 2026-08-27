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

from datetime import timedelta

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
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_chinita_2026")
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

API_URL = f"{PUBLIC_URL.rstrip('/')}/bot/post" if PUBLIC_URL else "http://localhost:5000/bot/post"

START_TIME = time.time()

TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if not os.path.exists("static"):
    os.makedirs("static")

# ==================== ESTADOS PARA CONVERSACIÓN ====================
WAITING_LINK = 1
WAITING_NAME = 2
WAITING_STORE_NAME = 3
WAITING_STORE_PRICE = 4
WAITING_STORE_DESC = 5
WAITING_STORE_LINK = 6
WAITING_KEYS_COUNT = 7

# ==================== FUNCIONES JSON ====================
def load_json(file):
    if not os.path.exists(file):
        return []
    try:
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_posts(): return load_json(DB_FILE)
def save_posts(d): save_json(DB_FILE, d)
def load_keys(): return load_json(KEYS_FILE)
def save_keys(d): save_json(KEYS_FILE, d)
def load_store(): return load_json(STORE_FILE)
def save_store(d): save_json(STORE_FILE, d)

def gen_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))

def get_video_id(url):
    if not url:
        return None
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return None

# ==================== SEGURIDAD WEB ====================
@app.before_request
def proteger():
    libres = ["/", "/bot/post", "/webhook", "/logout", "/gato", "/downloader"]
    if request.path.startswith("/static"):
        return
    if request.path in libres:
        return
    if not session.get("login"):
        return redirect("/")
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
                    keys.remove(key)
                    save_keys(keys)
                session.permanent = True
                session["login"] = True
                return redirect("/panel")
        return render_template("index.html", error="❌ Login incorrecto")
    return render_template("index.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

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

# ==================== ENDPOINT PARA EL BOT (SOLO REGISTRA) ====================
@app.route("/bot/post", methods=["POST"])
def bot_post():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data"}), 400
        
        # ✅ SOLO REGISTRAMOS, NO GUARDAMOS 2 VECES
        # El guardado ya lo hace la conversación
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== BOT ====================
def is_admin(update):
    try:
        return update.effective_user.id == ADMIN_ID
    except:
        return False

# ==================== MENÚ PRINCIPAL ====================
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ No autorizado")
        return
    
    keyboard = [
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await update.message.reply_text(
        "🤖 **PAPI DEXTER BOT**\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== MENÚ YOUTUBE ====================
async def menu_yt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Agregar Video", callback_data="yt_add_start")],
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

# ==================== AGREGAR VIDEO (SIN COMANDOS) ====================
async def yt_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    await query.edit_message_text(
        "📥 **AGREGAR VIDEO**\n\n"
        "📌 **PASO 1:** Envía el **link de YouTube**\n\n"
        "Ejemplo:\n"
        "`https://youtu.be/xxxxx` o `https://www.youtube.com/watch?v=xxxxx`\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    ctx.user_data['yt_step'] = 'waiting_link'
    return WAITING_LINK

async def yt_receive_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    link = update.message.text.strip()
    
    # Validar link de YouTube
    if not get_video_id(link):
        await update.message.reply_text(
            "❌ **Link inválido**\n\n"
            "Envía un link válido de YouTube:\n"
            "`https://youtu.be/xxxxx`\n"
            "`https://www.youtube.com/watch?v=xxxxx`",
            parse_mode="Markdown"
        )
        return WAITING_LINK
    
    ctx.user_data['yt_link'] = link
    ctx.user_data['yt_step'] = 'waiting_name'
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="yt_cancel")]]
    
    await update.message.reply_text(
        f"✅ **Link guardado:**\n`{link}`\n\n"
        "📌 **PASO 2:** Envía el **nombre del archivo**\n\n"
        "Ejemplo:\n"
        "`video_skin`\n\n"
        "📁 Se guardará como: `video_skin.unity3d`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_NAME

async def yt_receive_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        await update.message.reply_text(
            "❌ **Nombre inválido**\n\n"
            "El nombre debe tener al menos 2 caracteres.\n"
            "Ejemplo: `video_skin`",
            parse_mode="Markdown"
        )
        return WAITING_NAME
    
    link = ctx.user_data.get('yt_link')
    
    if not link:
        await update.message.reply_text("❌ Error: No hay link guardado. Vuelve a empezar.")
        return
    
    # ✅ GUARDAR SOLO UNA VEZ AQUÍ
    posts = load_posts()
    vid = get_video_id(link)
    thumb = f"https://img.youtube.com/vi/{vid}/0.jpg" if vid else None
    
    posts.append({
        "youtube": link,
        "file": name,
        "thumbnail": thumb,
        "created": time.time()
    })
    save_posts(posts)
    
    # ✅ SOLO NOTIFICAR AL WEBHOOK (SIN GUARDAR DE NUEVO)
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(API_URL, json={"youtube": link, "file": name})
    except:
        pass
    
    await update.message.reply_text(
        f"✅ **VIDEO PUBLICADO**\n\n"
        f"📹 **Link:** {link}\n"
        f"📁 **Archivo:** `{name}`\n"
        f"🖼️ **Thumbnail:** {thumb}\n\n"
        f"📌 Para agregar otro, usa /start",
        parse_mode="Markdown"
    )
    
    ctx.user_data.clear()
    return -1

async def yt_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Operación cancelada**\n\n"
        "Usa /start para volver al menú principal.",
        parse_mode="Markdown"
    )
    return -1

# ==================== LISTAR VIDEOS ====================
async def yt_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos guardados.")
        return
    
    txt = "📋 **VIDEOS GUARDADOS:**\n\n"
    for i, p in enumerate(posts):
        nombre = p.get('file', 'sin nombre')
        txt += f"{i}. `{nombre}`\n"
    
    if len(txt) > 4000:
        txt = txt[:3900] + "\n... (demasiados videos)"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== ELIMINAR VIDEO ====================
async def yt_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    posts = load_posts()
    if not posts:
        await query.edit_message_text("📋 No hay videos para eliminar.")
        return
    
    keyboard = []
    for i, p in enumerate(posts):
        nombre = p.get('file', f'video_{i}')
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {nombre[:20]}", callback_data=f"del_yt_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA VIDEO A ELIMINAR:**",
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
            await query.edit_message_text(f"✅ Video eliminado: `{removed.get('file', 'sin nombre')}`")
        else:
            await query.edit_message_text("❌ Error: Video no encontrado")
    except:
        await query.edit_message_text("❌ Error al eliminar")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_yt")]]
    await query.edit_message_text(
        "🗑️ **ELIMINADO**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== LIMPIAR VIDEOS ====================
async def yt_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI, limpiar todo", callback_data="yt_clear_confirm")],
        [InlineKeyboardButton("❌ NO, cancelar", callback_data="menu_yt")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODOS LOS VIDEOS?**\n\nEsta acción no se puede deshacer.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def yt_clear_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    save_posts([])
    await query.edit_message_text("🧹 Todos los videos eliminados.")

# ==================== MENÚ TIENDA ====================
async def menu_store(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Agregar Producto", callback_data="store_add_start")],
        [InlineKeyboardButton("📋 Listar Productos", callback_data="store_list")],
        [InlineKeyboardButton("🗑️ Eliminar Producto", callback_data="store_delete")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🛒 **GESTIÓN DE TIENDA**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== AGREGAR PRODUCTO (SIN COMANDOS) ====================
async def store_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
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
    
    ctx.user_data['store_step'] = 'waiting_name'
    return WAITING_STORE_NAME

async def store_receive_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        await update.message.reply_text("❌ Nombre inválido (mínimo 2 caracteres)")
        return WAITING_STORE_NAME
    
    ctx.user_data['store_name'] = name
    ctx.user_data['store_step'] = 'waiting_price'
    
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
        return
    
    price = update.message.text.strip()
    
    if not price:
        await update.message.reply_text("❌ Precio inválido")
        return WAITING_STORE_PRICE
    
    ctx.user_data['store_price'] = price
    ctx.user_data['store_step'] = 'waiting_desc'
    
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
        return
    
    desc = update.message.text.strip()
    
    if not desc or len(desc) < 3:
        await update.message.reply_text("❌ Descripción inválida (mínimo 3 caracteres)")
        return WAITING_STORE_DESC
    
    ctx.user_data['store_desc'] = desc
    ctx.user_data['store_step'] = 'waiting_link'
    
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
        return
    
    link = update.message.text.strip()
    
    if not link or not link.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Link inválido. Debe comenzar con http:// o https://")
        return WAITING_STORE_LINK
    
    # Guardar producto
    data = load_store()
    data.append({
        "nombre": ctx.user_data.get('store_name'),
        "precio": ctx.user_data.get('store_price'),
        "descripcion": ctx.user_data.get('store_desc'),
        "link": link,
        "imagen": None
    })
    save_store(data)
    
    await update.message.reply_text(
        f"✅ **PRODUCTO CREADO**\n\n"
        f"📦 **Nombre:** `{ctx.user_data.get('store_name')}`\n"
        f"💰 **Precio:** `{ctx.user_data.get('store_price')}`\n"
        f"📄 **Descripción:** {ctx.user_data.get('store_desc')}\n"
        f"🔗 **Link:** {link}\n\n"
        "📸 Ahora **envía una imagen** para el producto (opcional).",
        parse_mode="Markdown"
    )
    
    ctx.user_data.clear()
    return -1

async def store_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Operación cancelada**\n\n"
        "Usa /start para volver al menú principal.",
        parse_mode="Markdown"
    )
    return -1

# ==================== LISTAR PRODUCTOS ====================
async def store_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 No hay productos en la tienda.")
        return
    
    txt = "🛒 **PRODUCTOS:**\n\n"
    for i, p in enumerate(data):
        txt += f"{i}. **{p.get('nombre', 'sin nombre')}** | ${p.get('precio', '0')}\n"
        if p.get('descripcion'):
            txt += f"   {p.get('descripcion')[:50]}...\n"
        txt += "\n"
    
    if len(txt) > 4000:
        txt = txt[:3900] + "\n... (demasiados productos)"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== ELIMINAR PRODUCTO ====================
async def store_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_store()
    if not data:
        await query.edit_message_text("🛒 No hay productos para eliminar.")
        return
    
    keyboard = []
    for i, p in enumerate(data):
        nombre = p.get('nombre', f'producto_{i}')
        keyboard.append([InlineKeyboardButton(f"🗑️ {i} - {nombre[:20]}", callback_data=f"del_store_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="menu_store")])
    
    await query.edit_message_text(
        "🗑️ **SELECCIONA PRODUCTO A ELIMINAR:**",
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
            await query.edit_message_text(f"✅ Producto eliminado: `{removed.get('nombre', 'sin nombre')}`")
        else:
            await query.edit_message_text("❌ Error: Producto no encontrado")
    except:
        await query.edit_message_text("❌ Error al eliminar")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_store")]]
    await query.edit_message_text(
        "🗑️ **ELIMINADO**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== MENÚ KEYS ====================
async def menu_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔑 Generar Keys", callback_data="keys_gen_start")],
        [InlineKeyboardButton("📋 Ver Keys", callback_data="keys_list")],
        [InlineKeyboardButton("🗑️ Eliminar Keys", callback_data="keys_del")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "🔑 **GESTIÓN DE KEYS**\n\nSelecciona una acción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== GENERAR KEYS (SIN COMANDOS) ====================
async def keys_gen_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="keys_cancel")]]
    
    await query.edit_message_text(
        "🔑 **GENERAR KEYS**\n\n"
        "📌 Envía la **cantidad de keys** que deseas generar\n\n"
        "Ejemplo:\n"
        "`5`\n"
        "`10`\n"
        "`20`\n\n"
        "🔴 Presiona 'Cancelar' para salir.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return WAITING_KEYS_COUNT

async def keys_receive_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    try:
        n = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ **Cantidad inválida**\n\nEnvía un número válido.\nEjemplo: `5`", parse_mode="Markdown")
        return WAITING_KEYS_COUNT
    
    if n < 1:
        await update.message.reply_text("❌ La cantidad debe ser mayor a 0")
        return WAITING_KEYS_COUNT
    
    if n > 100:
        await update.message.reply_text("❌ Máximo 100 keys por vez")
        return WAITING_KEYS_COUNT
    
    keys = load_keys()
    nuevas = [gen_key() for _ in range(n)]
    keys.extend(nuevas)
    save_keys(keys)
    
    txt = "\n".join(nuevas)
    file = io.BytesIO(txt.encode())
    file.name = "keys.txt"
    
    await update.message.reply_document(
        InputFile(file, filename="keys.txt"),
        caption=f"✅ **{n} KEYS GENERADAS**\n\n📁 Archivo adjunto con todas las keys.",
        parse_mode="Markdown"
    )
    
    ctx.user_data.clear()
    return -1

async def keys_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ctx.user_data.clear()
    
    await query.edit_message_text(
        "❌ **Operación cancelada**\n\n"
        "Usa /start para volver al menú principal.",
        parse_mode="Markdown"
    )
    return -1

# ==================== LISTAR KEYS ====================
async def keys_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keys = load_keys()
    if not keys:
        await query.edit_message_text("🔑 No hay keys generadas.")
        return
    
    txt = "🔑 **KEYS GENERADAS:**\n\n"
    for i, k in enumerate(keys):
        txt += f"{i+1}. `{k}`\n"
    
    if len(txt) > 4000:
        txt = txt[:3900] + "\n... (demasiadas keys)"
    
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="menu_keys")]]
    
    await query.edit_message_text(
        txt,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== ELIMINAR KEYS ====================
async def keys_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ SI, eliminar todas", callback_data="keys_del_confirm")],
        [InlineKeyboardButton("❌ NO, cancelar", callback_data="menu_keys")]
    ]
    
    await query.edit_message_text(
        "⚠️ **¿ELIMINAR TODAS LAS KEYS?**\n\nEsta acción no se puede deshacer.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def keys_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    save_keys([])
    await query.edit_message_text("🗑️ Todas las keys eliminadas.")

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

🤖 Bot de gestión para Unity Assets

📌 **Funciones:**
• Gestión de videos YouTube
• Tienda de productos
• Generación de keys
• Estadísticas en tiempo real

👤 Admin: PAPI DEXTER

⚡ Versión 3.0 - Sin comandos, solo conversación"""
    
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
        [InlineKeyboardButton("📹 YouTube", callback_data="menu_yt")],
        [InlineKeyboardButton("🛒 Tienda", callback_data="menu_store")],
        [InlineKeyboardButton("🔑 Keys", callback_data="menu_keys")],
        [InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="menu_info")]
    ]
    
    await query.edit_message_text(
        "🤖 **PAPI DEXTER BOT**\n\nSelecciona una opción:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==================== FOTO HANDLER ====================
async def foto_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    if not update.message.photo:
        return
    
    try:
        file = await update.message.photo[-1].get_file()
        filename = f"store_{int(time.time())}_{random.randint(1000,9999)}.jpg"
        path = os.path.join("static", filename)
        await file.download_to_drive(path)
        
        data = load_store()
        if data:
            for i in range(len(data) - 1, -1, -1):
                if not data[i].get("imagen"):
                    data[i]["imagen"] = "/" + path
                    save_store(data)
                    await update.message.reply_text(f"✅ Imagen guardada para: `{data[i]['nombre']}`", parse_mode="Markdown")
                    return
            
            await update.message.reply_text("❌ Todos los productos ya tienen imagen")
            if os.path.exists(path):
                os.remove(path)
        else:
            await update.message.reply_text("❌ No hay productos en la tienda")
            if os.path.exists(path):
                os.remove(path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ==================== CONFIGURACIÓN DEL BOT ====================
def setup_bot():
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Comandos - SOLO /start
    bot.add_handler(CommandHandler("start", start_cmd))
    
    # ===== CONVERSACIÓN: AGREGAR VIDEO =====
    yt_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(yt_add_start, pattern="^yt_add_start$")],
        states={
            WAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_link)],
            WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, yt_receive_name)],
        },
        fallbacks=[CallbackQueryHandler(yt_cancel, pattern="^yt_cancel$")]
    )
    bot.add_handler(yt_conv)
    
    # ===== CONVERSACIÓN: AGREGAR PRODUCTO =====
    store_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(store_add_start, pattern="^store_add_start$")],
        states={
            WAITING_STORE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_name)],
            WAITING_STORE_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_price)],
            WAITING_STORE_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_desc)],
            WAITING_STORE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, store_receive_link)],
        },
        fallbacks=[CallbackQueryHandler(store_cancel, pattern="^store_cancel$")]
    )
    bot.add_handler(store_conv)
    
    # ===== CONVERSACIÓN: GENERAR KEYS =====
    keys_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(keys_gen_start, pattern="^keys_gen_start$")],
        states={
            WAITING_KEYS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, keys_receive_count)],
        },
        fallbacks=[CallbackQueryHandler(keys_cancel, pattern="^keys_cancel$")]
    )
    bot.add_handler(keys_conv)
    
    # Callbacks - Menú Principal
    bot.add_handler(CallbackQueryHandler(menu_yt, pattern="^menu_yt$"))
    bot.add_handler(CallbackQueryHandler(menu_store, pattern="^menu_store$"))
    bot.add_handler(CallbackQueryHandler(menu_keys, pattern="^menu_keys$"))
    bot.add_handler(CallbackQueryHandler(menu_stats, pattern="^menu_stats$"))
    bot.add_handler(CallbackQueryHandler(menu_info, pattern="^menu_info$"))
    bot.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    
    # Callbacks - YouTube
    bot.add_handler(CallbackQueryHandler(yt_list, pattern="^yt_list$"))
    bot.add_handler(CallbackQueryHandler(yt_delete, pattern="^yt_delete$"))
    bot.add_handler(CallbackQueryHandler(yt_clear, pattern="^yt_clear$"))
    bot.add_handler(CallbackQueryHandler(yt_delete_confirm, pattern="^del_yt_"))
    bot.add_handler(CallbackQueryHandler(yt_clear_confirm, pattern="^yt_clear_confirm$"))
    
    # Callbacks - Store
    bot.add_handler(CallbackQueryHandler(store_list, pattern="^store_list$"))
    bot.add_handler(CallbackQueryHandler(store_delete, pattern="^store_delete$"))
    bot.add_handler(CallbackQueryHandler(store_delete_confirm, pattern="^del_store_"))
    
    # Callbacks - Keys
    bot.add_handler(CallbackQueryHandler(keys_list, pattern="^keys_list$"))
    bot.add_handler(CallbackQueryHandler(keys_del, pattern="^keys_del$"))
    bot.add_handler(CallbackQueryHandler(keys_del_confirm, pattern="^keys_del_confirm$"))
    
    # Mensajes - Fotos
    bot.add_handler(MessageHandler(filters.PHOTO, foto_handler))
    
    return bot

# ==================== MAIN ====================
async def run_bot():
    bot = setup_bot()
    await bot.initialize()
    await bot.start()
    print("✅ Bot iniciado - SIN COMANDOS, solo conversación")
    await bot.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=lambda: asyncio.run(run_bot()), daemon=True)
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)