<div align="center">⚡ DEXTER MODZ

"WEB • TELEGRAM BOT • FILES • STORE • AUTOMATION"

<img src="assets/creator-logo.png" width="120" alt="DEXTER MODZ Creator Logo">Una plataforma creada para centralizar contenido, automatización y herramientas digitales.

""Python" (https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)" (#)
""Flask" (https://img.shields.io/badge/Flask-Web-000000?style=for-the-badge&logo=flask&logoColor=white)" (#)
""Telegram" (https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)" (#)

</div>---

🖤 ¿Qué es DEXTER MODZ?

DEXTER MODZ es una plataforma web conectada con un bot de Telegram, creada para administrar publicaciones, archivos, productos y diferentes herramientas desde un único sistema.

El proyecto combina un panel web, una API, un bot de Telegram y almacenamiento basado en archivos JSON.

La idea es mantener un sistema rápido, sencillo y fácil de administrar.

---

⚡ Características

Función| Descripción
🔐 Login| Sistema de acceso protegido
📂 Files| Administración de publicaciones
🛒 Store| Catálogo de productos
🤖 Downloader| Acceso a herramientas de descarga
🎮 Game| Sección de entretenimiento
🔑 Keys| Generación y administración de claves
📡 API| Comunicación entre el bot y la web
🤖 Telegram| Administración mediante comandos
🌌 UI| Interfaz futurista y responsive

---

🤖 Telegram Bot

El bot permite controlar gran parte de la plataforma directamente desde Telegram.

📌 Comandos

/start
/yt
/list
/delete
/clear

/addstore
/liststore
/delstore

/stats
/ping
/uptime

/genkey
/delkeysall

📤 Publicar contenido

/yt LINK_YOUTUBE LINK_ARCHIVO

El bot envía la información a la API y la publicación queda almacenada para mostrarse posteriormente en la web.

---

🌐 Panel de administración

El panel funciona como el centro principal de DEXTER MODZ.

╭────────────────────────────╮
│      DEXTER MODZ PANEL     │
├────────────────────────────┤
│ 📂 FILES                   │
│ 🛒 STORE                   │
│ 🤖 DOWNLOADER              │
│ 🍀 WHATSAPP CHANNEL        │
│ 🎮 GAME                    │
╰────────────────────────────╯

---

🔐 Sistema de acceso

El proyecto incorpora diferentes mecanismos de protección:

Usuario + Contraseña
        │
        ▼
    Access Key
        │
        ▼
   Flask Session
        │
        ▼
   🔓 PANEL ACCESS

También existe una Master Key para el acceso administrativo.

---

🧩 Arquitectura

                    ┌─────────────────┐
                    │   TELEGRAM 🤖   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    BOT API 📡   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │      FLASK      │
                    │      SERVER     │
                    └────────┬────────┘
                             │
                  ┌──────────┼──────────┐
                  ▼          ▼          ▼
              database    keys       store
                .json      .json       .json
                  │          │          │
                  └──────────┼──────────┘
                             ▼
                    ┌─────────────────┐
                    │    WEB PANEL 🌐 │
                    └─────────────────┘

---

🌑 CREATOR

<div align="center"><img src="assets/jinwoo.png" width="220" alt="Sung Jin-Woo">⚔️ DEXTER MODZ

Creator & Developer

«"ARISE."»

Powered by creativity, code and late-night debugging.

</div>---

🛠️ Tecnologías

🐍 Python
🌐 Flask
🤖 python-telegram-bot
📡 aiohttp
🎮 UnityPy
🗄️ JSON
🎨 HTML
⚡ CSS
🧠 JavaScript

---

📁 Estructura

DEXTER-MODZ/
│
├── app.py
├── requirements.txt
│
├── templates/
│   ├── index.html
│   ├── panel.html
│   ├── posts.html
│   ├── store.html
│   ├── downloader.html
│   └── gato.html
│
├── static/
│   └── ...
│
├── database.json
├── keys.json
├── store.json
│
├── assets/
│   ├── creator-logo.png
│   └── jinwoo.png
│
└── README.md

---

🚀 Instalación

1. Clonar el proyecto

git clone TU_REPOSITORIO
cd DEXTER-MODZ

2. Instalar dependencias

pip install -r requirements.txt

3. Configurar variables

BOT_TOKEN=TU_TOKEN
PUBLIC_URL=TU_URL
SECRET_KEY=TU_SECRET
MASTER_KEY=TU_MASTER_KEY

4. Ejecutar

python app.py

---

📡 Flujo de publicación

👤 ADMIN
   │
   │ /yt
   ▼
🤖 TELEGRAM BOT
   │
   ▼
📡 /bot/post
   │
   ▼
🐍 FLASK
   │
   ▼
🗄️ database.json
   │
   ▼
🌐 FILES

---

⚡ Estado del proyecto

████████████████████████████  ONLINE

WEB       ████████████████████  READY
BOT       ████████████████████  READY
API       ████████████████████  READY
STORE     ████████████████████  READY
FILES     ████████████████████  READY

---

🖤 DEXTER MODZ

No es solamente una página.

Es un sistema construido para reunir:

        CODE
         +
       DESIGN
         +
      AUTOMATION
         +
       TELEGRAM
         +
        WEB
         ↓
   ┌───────────────┐
   │ DEXTER MODZ ⚡ │
   └───────────────┘

<div align="center">⚔️ "ARISE."

DEXTER MODZ © 2026

</div>
