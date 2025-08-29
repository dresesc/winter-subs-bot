import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatMember
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, MessageHandler, ChatMemberHandler, filters
from datetime import datetime, timedelta
)
from datetime import datetime, timedelta
import pytz 

COLOMBIA_TZ = pytz.timezone("America/Bogota")

# ========= CONFIG =========
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6943566239
DATABASE_URL = os.getenv("DATABASE_URL")

WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # ej: https://mi-bot.onrender.com
WEBHOOK_PORT = int(os.getenv("PORT", "8443"))

GROUP_LINK = "https://t.me/+hv3Rlu5sQCE5OWVh"

# ========= BASE DE DATOS =========
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # tabla de suscripciones
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            tipo TEXT,
            vence DATE
        )
    """)
    # tabla de miembros
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            last_seen TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def add_user(user_id, username, tipo, dias=None):
    conn = get_conn()
    cur = conn.cursor()
    vence = None
    if dias:
        vence = (datetime.now(COLOMBIA_TZ) + timedelta(days=dias)).date()
    cur.execute("""
        INSERT INTO users (user_id, username, tipo, vence)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET username = EXCLUDED.username,
            tipo = EXCLUDED.tipo,
            vence = EXCLUDED.vence
    """, (user_id, username, tipo, vence))
    conn.commit()
    cur.close()
    conn.close()

def remove_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return deleted


def get_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, tipo, vence FROM users WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, tipo, vence FROM users WHERE LOWER(username)=LOWER(%s)",
        (username,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, tipo, vence FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def update_member(user_id, username, full_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO members (user_id, username, full_name, last_seen)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE
        SET username = EXCLUDED.username,
            full_name = EXCLUDED.full_name,
            last_seen = NOW()
    """, (user_id, username, full_name))
    conn.commit()
    cur.close()
    conn.close()

def get_member_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, full_name FROM members WHERE LOWER(username)=LOWER(%s)",
        (username,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

def get_member_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, full_name FROM members WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

# ========= HELPERS =========
def username_or_id(username, user_id):
    return f"@{username}" if username else str(user_id)

async def resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """resolver usuario desde reply, @usuario o ID (buscando en members, users o get_chat)."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    if not context.args:
        return None

    arg = context.args[0]

    # Caso: ID numérico
    if arg.isdigit():
        uid = int(arg)

        # buscar en members
        m = get_member_by_id(uid)
        if m:
            class T: pass
            u = T(); u.id, u.username, u.full_name = m
            return u

        # buscar en users
        udb = get_user(uid)
        if udb:
            uname, _, _ = udb
            class T: pass
            u = T(); u.id = uid; u.username = uname; u.full_name = uname or str(uid)
            return u

        # fallback a Telegram
        try:
            return await context.bot.get_chat(uid)
        except:
            return None

    # Caso: @username
    username_arg = arg.lstrip("@")

    # buscar en members
    m = get_member_by_username(username_arg)
    if m:
        class T: pass
        u = T(); u.id, u.username, u.full_name = m
        return u

    # buscar en users
    udb = get_user_by_username(username_arg)
    if udb:
        uid, uname, _, _ = udb
        class T: pass
        u = T(); u.id = uid; u.username = uname; u.full_name = uname or str(uid)
        return u

    # fallback a Telegram (usar arroba)
    try:
        return await context.bot.get_chat("@" + username_arg)
    except:
        return None


# ========= HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type == "private":
        await update.message.reply_text(
            "𓈒 ࣪ ˖ ¡holi! soy el bot encargado de gestionar tu suscripción dentro de 𝔀inter 𝓹riv. ♪ 🪽🪽 \n"
            "usa el comando /help para que pueda ayudarte."
        )

async def sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2 and not update.message.reply_to_message:
        await update.message.reply_text("uso: /sub @usuario {días}")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("no se pudo encontrar al usuario.")
        return

    try:
        dias = int(context.args[1]) if len(context.args) > 1 else 30
    except ValueError:
        await update.message.reply_text("los días deben ser un número.")
        return

    add_user(user.id, user.username or user.full_name, "premium", dias)
    fecha_vencimiento = (datetime.now(COLOMBIA_TZ) + timedelta(days=dias)).strftime("%d/%m/%Y")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! se han añadido {dias} día(s) a tu suscripción premium.\n"
        f"🪽⊹ tu cupo vence el {fecha_vencimiento}"
    )

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("uso: /free @usuario")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("no se pudo encontrar al usuario.")
        return

    add_user(user.id, user.username or user.full_name, "free")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! eres cupo free dentro de 𝔀inter 𝓹riv. "
        "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo. ❤︎"
    )

async def addmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("uso: /addmod @usuario (o responde a su mensaje).")
        return

    add_user(user.id, user.username or user.full_name, "mod")
    await update.message.reply_text(
        f"¡hola, {user.full_name}! ahora eres parte del staff "
        "con cupo ilimitado dentro de 𝔀inter 𝓹riv. 🪽⊹"
    )

async def rmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("uso: /unmod @usuario (o responde a su mensaje).")
        return

    remove_user(user.id)
    await update.message.reply_text(f"{username_or_id(user.username, user.id)} ha sido removido del staff de 𝔀inter 𝓹riv.")


async def rsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # debe venir un argumento y ser un número
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("uso: /rsub user_id")
        return

    uid = int(context.args[0])

    try:
        conn = get_conn()
        cur = conn.cursor()

        # eliminar de users
        cur.execute("DELETE FROM users WHERE user_id=%s", (uid,))
        deleted_users = cur.rowcount

        # eliminar de members
        cur.execute("DELETE FROM members WHERE user_id=%s", (uid,))
        deleted_members = cur.rowcount

        conn.commit()
        cur.close()
        conn.close()

        if deleted_users or deleted_members:
            await update.message.reply_text(
                f"{uid} fue removido de 𝔀inter 𝓹riv. "
            )
        else:
            await update.message.reply_text(f"{uid} no estaba en la base de datos.")
    except Exception as e:
        await update.message.reply_text(f"error al remover usuario: {e}")

async def mysub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user.id == ADMIN_ID:
        await update.message.reply_text("blud eres el owner.")
        return

    sub = get_user(user.id)
    if not sub:
        await update.message.reply_text("no tienes ninguna suscripción activa.")
        return

    username, tipo, vence = sub
    nombre = user.full_name

    if tipo == "premium":
        dias = (vence - datetime.now(COLOMBIA_TZ).date()).days if vence else None
        await update.message.reply_text(
            f"¡hola, {nombre}! eres cupo premium dentro de 𝔀inter 𝓹riv.\n\n"
            f"🪽⊹ tu cupo vence el {vence.strftime('%d/%m/%Y') if vence else 'desconocido'}\n"
            f"te quedan {dias if dias is not None else '??'} día(s) con nosotros."
        )
    elif tipo == "free":
        await update.message.reply_text(
            f"¡hola, {nombre}! eres cupo free dentro de 𝔀inter 𝓹riv. "
            "recuerda mandar un mínimo 4 referencias semanales para continuar con tu cupo. ❤︎"
        )
    elif tipo == "mod":
        await update.message.reply_text(
            f"¡hola, {nombre}! eres parte del staff en 𝔀inter 𝓹riv. "
            "tu cupo es ilimitado mientras seas parte de nuestra administración. 🪽⊹"
        )


async def listmods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    usuarios = get_all_users()
    mods = [f"- {username_or_id(username, user_id)}" for user_id, username, tipo, vence in usuarios if tipo == "mod"]

    if not mods:
        await update.message.reply_text("no hay miembros del staff registrados.")
    else:
        await update.message.reply_text("𝓐dministración\n" + "\n".join(mods))

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    usuarios = get_all_users()
    if not usuarios:
        await update.message.reply_text("no hay usuarios registrados en la base de datos.")
        return

    texto = "𝓜iembros\n"
    for user_id, username, tipo, vence in usuarios:
        nombre = username_or_id(username, user_id)

        if tipo == "premium":
            texto += f"- {nombre} | premium (vence: {vence.strftime('%d/%m/%Y') if vence else '??'})\n"
        elif tipo == "free":
            texto += f"- {nombre} | free\n"
        elif tipo == "mod":
            texto += f"- {nombre} | staff (mod)\n"

    await update.message.reply_text(texto)

async def whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("uso: /whois @usuario (o responde a su mensaje).")
        return

    user = await resolve_target(update, context)
    if not user:
        await update.message.reply_text("usuario no encontrado en la base de datos.")
        return

    sub = get_user(user.id)
    if not sub:
        await update.message.reply_text(f"{username_or_id(user.username, user.id)} no tiene suscripción activa.")
        return

    username, tipo, vence = sub
    nombre = username_or_id(username, user.id)

    if tipo == "premium":
        await update.message.reply_text(
            f"{nombre} tiene suscripción premium hasta el {vence.strftime('%d/%m/%Y') if vence else 'desconocido'}."
        )
    elif tipo == "free":
        await update.message.reply_text(f"{nombre} tiene cupo free.")
    elif tipo == "mod":
        await update.message.reply_text(f"{nombre} es admin del priv.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "᭝ ᨳଓ ՟ /buy = ¿primera vez con nosotros? usa este comando para adquirir tu cupo premium. ¡anímate a ser parte de esta linda comunidad!\n\n"
        
        "᭝ ᨳଓ ՟ /renew = usa este comando para renovar tu cupo premium.\n\n"
        
        "᭝ ᨳଓ ՟ /mysub = muestra el estado actual de tu suscripción en nuestro priv."
    )

def plan_keyboard(tipo="buy"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("15 días : 20 robux", callback_data=f"{tipo}_plan_15")],
        [InlineKeyboardButton("30 días : 55 robux", callback_data=f"{tipo}_plan_30")],
        [InlineKeyboardButton("45 días : 80 robux", callback_data=f"{tipo}_plan_45")],
        [InlineKeyboardButton("¿otro método de pago?", url="https://t.me/minangels")]
    ])

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "𝓦inter 𝓟riv 𓂋 🪽\n"
        "¡muchísimas gracias por querer adquirir nuestros servicios y apoyar este proyecto! este priv hará lo mejor para guiarte en este mundo del bineo.\n\n"
        
        "໒꒱ elige el plan que desees y que sea más accesible para ti. recuerda que todos nuestros planes cuentan con los mismos beneficios.",
        reply_markup=plan_keyboard("buy")
    )

async def renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sub = get_user(update.effective_user.id)
    if not sub or sub[1] != "premium":
        await update.message.reply_text(
            "mmm… no tenías una suscripción premium activa anteriormente. debes usar el comando /buy."
        )
        return
    await update.message.reply_text(
        "𝓦inter 𝓟riv 𓂋 🪽\n"
        "¡muchísimas gracias por querer renovar nuestros servicios y apoyar este proyecto! este priv hará lo mejor para guiarte en este mundo del bineo.\n\n"
        
        "໒꒱ elige el plan que desees y que sea más accesible para ti. recuerda que todos nuestros planes cuentan con los mismos beneficios.",
        reply_markup=plan_keyboard("renew")
    )

PLAN_INFO = {
    "plan_15": ("𝓟remium 𝟭𝟱 𝓓ías", 15, "https://www.roblox.com/es/game-pass/1421913677/winter-priv-15-d-as"),
    "plan_30": ("𝓟remium 𝟯𝟬 𝓓ías", 30, "https://www.roblox.com/es/game-pass/1421828046/winter-priv-30-d-as"),
    "plan_45": ("𝓟remium 𝟰𝟱 𝓓ías", 45, "https://www.roblox.com/es/game-pass/1421941643/winter-priv-45-d-as"),
}

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("buy_") or data.startswith("renew_"):
        _, plan_key = data.split("_", 1)
        nombre, dias, link = PLAN_INFO[plan_key]

        texto = (
            f"{nombre}\n"
            f"¿cómo {'adquirir' if data.startswith('buy') else 'renovar'}?\n\n"

            "haz clic en el enlace de compra y toma un pantallazo que muestre que adquiriste el gamepass. "
            "asegúrate de que se vean tu nombre de usuario y la confirmación de compra, ¡y listo! "
            "envía la captura por este chat.\n\n"
            
            "𝄞 ojo : si la imagen tiene recortes o está editada, no se considerará legítima. "
            "en ese caso, deberás contactar al owner. @dresesc\n\n"
            
            f"link de compra : {link}\n\n"
            
            f"¡muchas gracias por {'adquirir' if data.startswith('buy') else 'renovar'} 𝔀inter 𝓹riv! "
            "disfruta tu estadía con nosotros."
        )

        # borrar SOLO el último mensaje de info de plan (si existe)
        prev_id = context.user_data.get("plan_info_msg_id")
        if prev_id:
            try:
                await context.bot.delete_message(
                    chat_id=query.message.chat.id,
                    message_id=prev_id
                )
            except Exception:
                pass

        # enviar nuevo mensaje con info del plan
        sent = await query.message.reply_text(texto)
        context.user_data["plan_info_msg_id"] = sent.message_id

        # guardar plan pendiente (días y si es renew) para photo_handler
        context.user_data["pending_plan"] = (dias, data.startswith("renew"))

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sub = get_user(user.id)
    if "pending_plan" not in context.user_data:
        return

    dias, is_renew = context.user_data["pending_plan"]

    caption = f"comprobante recibido de {user.full_name} (@{user.username or user.id})\n"
    if is_renew:
        caption += f"{user.id} renueva su suscripción en el priv."
    else:
        caption += f"{user.id} compra el priv por primera vez."

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✔️ aprobar", callback_data=f"approve_{user.id}_{dias}_{is_renew}"),
         InlineKeyboardButton("✖️ rechazar", callback_data=f"reject_{user.id}")]
    ])

    photo = update.message.photo[-1]
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo.file_id, caption=caption, reply_markup=markup)
    await update.message.reply_text("tu comprobante fue enviado al owner, espera aprobación. 🪽")

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    if data[0] == "approve":
        user_id = int(data[1]); dias = int(data[2]); is_renew = data[3] == "True"
        u = await context.bot.get_chat(user_id)
        add_user(user_id, u.username or u.full_name, "premium", dias)

        msg = "°˖➴ tu suscripción ha sido "
        if is_renew:
            msg += "renovada, ¡gracias por seguir confiando en nosotros!"
        else:
            msg += "activada.\n\n ¡ingresa a nuestro priv! " + GROUP_LINK

        await context.bot.send_message(user_id, msg)
        await query.edit_message_caption(caption="✔️ aprobado")
    elif data[0] == "reject":
        user_id = int(data[1])
        await context.bot.send_message(user_id, "tu comprobante fue rechazado por el owner. contacta a @dresesc")
        await query.edit_message_caption(caption="✖️ rechazado")

# ========= TRACKING =========
async def track_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        update_member(user.id, user.username, user.full_name)

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_member: ChatMember = update.chat_member
    user = chat_member.from_user
    if user:
        update_member(user.id, user.username, user.full_name)

# ========= RECORDATORIOS =========
async def reminder_job(context):
    usuarios = get_all_users()
    for user_id, username, tipo, vence in usuarios:
        if tipo == "premium" and vence:
            fecha_venc = vence
            if fecha_venc - timedelta(days=2) == datetime.now(COLOMBIA_TZ).date():
                try:
                    await context.bot.send_message(
                        user_id,
                        f"¡holi! tu suscripción vence el {fecha_venc.strftime('%d/%m/%Y')} "

                        "renueva con /renew o contacta a @dresesc 🎼"
                    )
                except:
                    pass

# ========= MAIN =========
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # comandos originales
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("sub", sub))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CommandHandler("addmod", addmod))
    app.add_handler(CommandHandler("rmod", rmod))
    app.add_handler(CommandHandler("rsub", rsub))
    app.add_handler(CommandHandler("mysub", mysub))
    app.add_handler(CommandHandler("listmods", listmods))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("whois", whois))

    # comandos nuevos
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("renew", renew))

    # botones y fotos
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^(buy_|renew_).*"))
    app.add_handler(CallbackQueryHandler(admin_buttons, pattern="^(approve_|reject_).*"))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # tracking y recordatorios
    app.add_handler(MessageHandler(filters.ALL, track_messages))
    app.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))
    app.job_queue.run_repeating(reminder_job, interval=86400, first=10)

    print("bot corriendo con WEBHOOK...")
    app.run_webhook(
        listen="0.0.0.0",
        port=WEBHOOK_PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )

if __name__ == "__main__":
    main()
