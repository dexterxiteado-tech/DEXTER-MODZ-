🖤 DEXTER MODZ

«Web + Bot + Sistema de gestión de contenido»

DEXTER MODZ es una plataforma web diseñada para centralizar y administrar contenido publicado mediante un bot de Telegram. El proyecto combina una interfaz web ligera con automatización para facilitar la publicación, gestión y distribución de archivos y recursos.

🚀 Características

- 🔐 Sistema de inicio de sesión
- 📂 Gestión de publicaciones
- 🛒 Tienda integrada
- 🤖 Bot de Telegram
- 🔑 Sistema de claves de acceso
- 📥 Publicación automática de contenido
- 🎮 Sección de juegos
- 📡 Comunicación mediante API
- 🌌 Interfaz estilo futurista
- ⚡ Diseño ligero y optimizado

🤖 Bot de Telegram

El bot permite administrar diferentes funciones del sistema directamente desde Telegram.

Comandos principales

/start       Información del bot
/yt          Publicar contenido
/list        Ver publicaciones
/delete      Eliminar una publicación
/clear        Eliminar todas las publicaciones

/addstore    Añadir producto
/liststore   Ver productos
/delstore    Eliminar producto

/stats       Estadísticas
/ping         Comprobar estado
/uptime      Tiempo activo

/genkey      Generar claves
/delkeysall  Eliminar todas las claves

🌐 Panel Web

El panel funciona como centro de administración de la plataforma.

Desde él se puede acceder a:

📂 FILES
🛒 STORE
🤖 DOWNLOADER
🍀 CHANNEL OF WHATSAPP
🎮 GAME

🔐 Seguridad

El sistema utiliza:

- Sesiones de Flask.
- Autenticación mediante usuario y contraseña.
- Claves de acceso.
- Clave maestra.
- Protección de las rutas privadas.
- Control de administrador para los comandos del bot.

📦 Estructura

DEXTER-MODZ/
│
├── app.py
├── panel.html
├── index.html
├── posts.html
├── store.html
├── downloader.html
├── gato.html
│
├── database.json
├── keys.json
├── store.json
│
├── static/
├── templates/
└── README.md

⚙️ Tecnologías

- 🐍 Python
- 🌐 Flask
- 🤖 python-telegram-bot
- 📡 aiohttp
- 🎮 UnityPy
- 🗄️ JSON
- 🎨 HTML / CSS / JavaScript

📡 Funcionamiento

El flujo principal del proyecto es:

Telegram
   │
   ▼
🤖 Bot
   │
   ▼
API /bot/post
   │
   ▼
Flask
   │
   ▼
database.json
   │
   ▼
🌐 Panel Web

Esto permite que una publicación enviada desde Telegram pueda aparecer posteriormente en la sección de archivos de la web.

💻 Instalación

Instala las dependencias:

pip install -r requirements.txt

Configura las variables necesarias:

BOT_TOKEN
PUBLIC_URL
SECRET_KEY
MASTER_KEY

Después ejecuta:

python app.py

🌌 DEXTER MODZ

Un proyecto pensado para combinar automatización, administración web y contenido digital en una sola plataforma.

╔══════════════════════════════╗
║        DEXTER MODZ           ║
║                              ║
║   WEB • BOT • FILES • STORE  ║
║                              ║
║        ⚡ SYSTEM ONLINE ⚡     ║
╚══════════════════════════════╝

📜 Licencia

Este proyecto es de uso personal y educativo. Respeta las licencias y derechos correspondientes de cualquier recurso de terceros que integres.
