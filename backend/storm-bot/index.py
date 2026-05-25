"""
Telegram-бот «Шторм» — обработчик webhook-запросов от Telegram.
Обрабатывает все команды и inline-кнопки бота.
"""
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
BOOST_COOLDOWN_MINUTES = 20

CARS = {
    1:  {"name": "Доминатор",  "emoji": "🚗", "price": 5000},
    2:  {"name": "Циклон",     "emoji": "🚙", "price": 8000},
    3:  {"name": "Ураган",     "emoji": "🚐", "price": 12000},
    4:  {"name": "Титан",      "emoji": "🛻", "price": 16000},
    5:  {"name": "Вихрь",      "emoji": "🚓", "price": 21000},
    6:  {"name": "Смерч",      "emoji": "🚕", "price": 26000},
    7:  {"name": "Тайфун",     "emoji": "🚌", "price": 31000},
    8:  {"name": "Гроза",      "emoji": "🏎", "price": 37000},
    9:  {"name": "Немезида",   "emoji": "🚑", "price": 43000},
    10: {"name": "Армагеддон", "emoji": "🚀", "price": 50000},
}

EF_DATA = {
    1: {"name": "EF1", "wind": "135–174 км/ч", "chance": 80, "reward": 300},
    2: {"name": "EF2", "wind": "175–217 км/ч", "chance": 65, "reward": 600},
    3: {"name": "EF3", "wind": "218–265 км/ч", "chance": 50, "reward": 1100},
    4: {"name": "EF4", "wind": "266–322 км/ч", "chance": 35, "reward": 2000},
    5: {"name": "EF5", "wind": "322+ км/ч",    "chance": 20, "reward": 4000},
}

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TG_API}/sendMessage", json=payload, timeout=10)


def answer_callback(callback_id, text="", alert=False):
    requests.post(f"{TG_API}/answerCallbackQuery", json={
        "callback_query_id": callback_id,
        "text": text,
        "show_alert": alert,
    }, timeout=5)


def edit_message(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    requests.post(f"{TG_API}/editMessageText", json=payload, timeout=10)


# ─── РАБОТА С БД ───

def get_or_create_user(conn, telegram_id: int, first_name: str = "Охотник"):
    with conn.cursor() as cur:
        cur.execute("SELECT telegram_id, name, balance, boost_used_at FROM users WHERE telegram_id = %s", (telegram_id,))
        row = cur.fetchone()
        if row:
            return {"telegram_id": row[0], "name": row[1], "balance": row[2], "boost_used_at": row[3]}
        cur.execute(
            "INSERT INTO users (telegram_id, name, balance) VALUES (%s, %s, 5000) RETURNING telegram_id, name, balance, boost_used_at",
            (telegram_id, first_name[:20])
        )
        row = cur.fetchone()
        conn.commit()
        return {"telegram_id": row[0], "name": row[1], "balance": row[2], "boost_used_at": row[3]}


def get_user_cars(conn, telegram_id: int):
    with conn.cursor() as cur:
        cur.execute("SELECT car_id, level, broken FROM user_cars WHERE telegram_id = %s ORDER BY car_id", (telegram_id,))
        return [{"car_id": r[0], "level": r[1], "broken": r[2]} for r in cur.fetchall()]


# ─── КОМАНДЫ ───

def cmd_start(conn, chat_id: int, first_name: str):
    user = get_or_create_user(conn, chat_id, first_name)
    text = (
        "🌪️ <b>ШТОРМ — Охотники за торнадо</b>\n\n"
        f"Добро пожаловать, <b>{user['name']}</b>!\n"
        "Ты — охотник на торнадо. Покупай машины-перехватчики,\n"
        "улучшай их и выезжай на охоту!\n\n"
        "💰 <b>Валюта:</b> Магшиормы (МШ)\n"
        f"💵 <b>Стартовый баланс:</b> {user['balance']:,} МШ\n\n"
        "<b>Команды:</b>\n"
        "/profil — профиль и баланс\n"
        "/shop — магазин машин\n"
        "/storm — охота на торнадо\n"
        "/name Имя — сменить имя\n\n"
        "Удачной охоты, сталкер! 🎯"
    )
    send(chat_id, text)


def cmd_name(conn, chat_id: int, new_name: str):
    new_name = new_name.strip()[:20]
    if not new_name:
        send(chat_id, "⚠️ Укажи имя: <code>/name ТвоёИмя</code>")
        return
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name = %s WHERE telegram_id = %s", (new_name, chat_id))
        conn.commit()
    send(chat_id, f"✅ Имя изменено на <b>{new_name}</b>!")


def cmd_profil(conn, chat_id: int):
    user = get_or_create_user(conn, chat_id)
    cars = get_user_cars(conn, chat_id)

    now = datetime.now(timezone.utc)
    boost_ready = True
    boost_text = "✅ Доступен!"
    if user["boost_used_at"]:
        delta = now - user["boost_used_at"].replace(tzinfo=timezone.utc) if user["boost_used_at"].tzinfo is None else now - user["boost_used_at"]
        remaining = timedelta(minutes=BOOST_COOLDOWN_MINUTES) - delta
        if remaining.total_seconds() > 0:
            boost_ready = False
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            boost_text = f"⏳ {mins}:{secs:02d}"

    car_lines = ""
    for c in cars[:5]:
        car = CARS[c["car_id"]]
        status = "🔴 сломана" if c["broken"] else f"Ур.{c['level']}"
        car_lines += f"  {car['emoji']} {car['name']} — {status}\n"
    if len(cars) > 5:
        car_lines += f"  ... и ещё {len(cars)-5} машин\n"
    if not cars:
        car_lines = "  Гараж пуст\n"

    text = (
        f"👤 <b>{user['name']}</b>\n"
        "─────────────────\n"
        f"💰 Баланс: <b>{user['balance']:,} МШ</b>\n"
        f"🚗 Машин в гараже: <b>{len(cars)}</b>\n\n"
        f"🚀 <b>ГАРАЖ:</b>\n{car_lines}\n"
        "─────────────────"
    )

    markup = {"inline_keyboard": [[
        {"text": f"⚡ Буст +200 МШ ({boost_text})", "callback_data": "boost"},
    ]]}
    send(chat_id, text, reply_markup=markup)


def cmd_shop(conn, chat_id: int, page: int = 0):
    cars_list = list(CARS.items())
    per_page = 3
    total_pages = (len(cars_list) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    user = get_or_create_user(conn, chat_id)
    owned = {c["car_id"] for c in get_user_cars(conn, chat_id)}

    text = f"🔧 <b>МАГАЗИН ПЕРЕХВАТЧИКОВ</b> (стр. {page+1}/{total_pages})\n"
    text += f"💰 Твой баланс: <b>{user['balance']:,} МШ</b>\n"
    text += "─────────────────\n"

    buttons = []
    for car_id, car in cars_list[page*per_page:(page+1)*per_page]:
        if car_id in owned:
            text += f"✅ {car['emoji']} <b>{car['name']}</b> — в гараже\n"
        else:
            text += f"🔒 {car['emoji']} <b>{car['name']}</b> — {car['price']:,} МШ\n"
            buttons.append([{"text": f"Купить {car['emoji']} {car['name']} ({car['price']:,} МШ)", "callback_data": f"buy_{car_id}"}])

    nav = []
    if page > 0:
        nav.append({"text": "◀️ Назад", "callback_data": f"shop_{page-1}"})
    if page < total_pages - 1:
        nav.append({"text": "Вперёд ▶️", "callback_data": f"shop_{page+1}"})
    if nav:
        buttons.append(nav)

    markup = {"inline_keyboard": buttons} if buttons else None
    send(chat_id, text, reply_markup=markup)


def cmd_shop_upgrade(conn, chat_id: int, page: int = 0):
    user = get_or_create_user(conn, chat_id)
    user_cars = get_user_cars(conn, chat_id)
    upgradeable = [c for c in user_cars if c["level"] < 3 and not c["broken"]]
    broken = [c for c in user_cars if c["broken"]]

    if not upgradeable and not broken:
        send(chat_id, "🔧 Нечего улучшать или ремонтировать.")
        return

    text = f"⚙️ <b>УЛУЧШЕНИЯ И РЕМОНТ</b>\n💰 Баланс: <b>{user['balance']:,} МШ</b>\n─────────────────\n"
    buttons = []

    for c in upgradeable:
        car = CARS[c["car_id"]]
        cost = car["price"] // 2 if c["level"] == 1 else car["price"]
        text += f"⚡ {car['emoji']} {car['name']} Ур.{c['level']} → Ур.{c['level']+1}: {cost:,} МШ\n"
        buttons.append([{"text": f"⚡ Улучшить {car['name']} ({cost:,} МШ)", "callback_data": f"upgrade_{c['car_id']}"}])

    for c in broken:
        car = CARS[c["car_id"]]
        text += f"🔴 {car['emoji']} {car['name']} — сломана (ремонт 500 МШ)\n"
        buttons.append([{"text": f"🔧 Починить {car['name']} (500 МШ)", "callback_data": f"repair_{c['car_id']}"}])

    send(chat_id, text, reply_markup={"inline_keyboard": buttons})


def cmd_storm(conn, chat_id: int):
    user_cars = get_user_cars(conn, chat_id)
    ready = [c for c in user_cars if not c["broken"]]

    if not ready:
        send(chat_id, "🚗 Нет готовых машин для охоты!\nКупи в /shop или почини в /shop")
        return

    text = "🌪️ <b>ОХОТА НА ТОРНАДО</b>\nВыбери машину-перехватчик:\n─────────────────\n"
    buttons = []
    for c in ready:
        car = CARS[c["car_id"]]
        bonus = (c["level"] - 1) * 10
        bonus_text = f" (+{bonus}%)" if bonus else ""
        text += f"{car['emoji']} <b>{car['name']}</b> Ур.{c['level']}{bonus_text}\n"
        buttons.append([{"text": f"{car['emoji']} {car['name']} Ур.{c['level']}{bonus_text}", "callback_data": f"hunt_{c['car_id']}"}])

    text += "\n<i>Шанс успеха зависит от уровня машины и категории торнадо</i>"
    send(chat_id, text, reply_markup={"inline_keyboard": buttons})


# ─── CALLBACK ОБРАБОТЧИКИ ───

def cb_boost(conn, chat_id: int, callback_id: str):
    user = get_or_create_user(conn, chat_id)
    now = datetime.now(timezone.utc)

    if user["boost_used_at"]:
        used_at = user["boost_used_at"]
        if used_at.tzinfo is None:
            used_at = used_at.replace(tzinfo=timezone.utc)
        delta = now - used_at
        if delta < timedelta(minutes=BOOST_COOLDOWN_MINUTES):
            remaining = timedelta(minutes=BOOST_COOLDOWN_MINUTES) - delta
            mins = int(remaining.total_seconds() // 60)
            secs = int(remaining.total_seconds() % 60)
            answer_callback(callback_id, f"⏳ Буст будет через {mins}:{secs:02d}", alert=True)
            return

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET balance = balance + 200, boost_used_at = %s WHERE telegram_id = %s",
            (now, chat_id)
        )
        conn.commit()

    answer_callback(callback_id, "⚡ +200 МШ получено!", alert=False)
    send(chat_id, f"⚡ <b>Буст активирован!</b>\n+200 МШ на счёт.\nСледующий буст через {BOOST_COOLDOWN_MINUTES} минут.")


def cb_buy(conn, chat_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, chat_id)
    car = CARS.get(car_id)
    if not car:
        answer_callback(callback_id, "Ошибка: машина не найдена", alert=True)
        return

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM user_cars WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
        if cur.fetchone():
            answer_callback(callback_id, "⚠️ Уже в гараже!", alert=True)
            return

        if user["balance"] < car["price"]:
            answer_callback(callback_id, f"❌ Недостаточно МШ! Нужно {car['price']:,}", alert=True)
            return

        cur.execute("UPDATE users SET balance = balance - %s WHERE telegram_id = %s", (car["price"], chat_id))
        cur.execute("INSERT INTO user_cars (telegram_id, car_id, level, broken) VALUES (%s, %s, 1, FALSE)", (chat_id, car_id))
        conn.commit()

    answer_callback(callback_id, f"✅ {car['name']} куплен!")
    send(chat_id, f"✅ <b>{car['emoji']} {car['name']}</b> добавлен в гараж!\n💰 Списано: <b>{car['price']:,} МШ</b>")


def cb_upgrade(conn, chat_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, chat_id)
    car = CARS.get(car_id)

    with conn.cursor() as cur:
        cur.execute("SELECT level, broken FROM user_cars WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
        row = cur.fetchone()
        if not row:
            answer_callback(callback_id, "Машина не найдена", alert=True)
            return
        level, broken = row

        if broken:
            answer_callback(callback_id, "⚠️ Сначала почини машину!", alert=True)
            return
        if level >= 3:
            answer_callback(callback_id, "★ Уже максимальный уровень!", alert=True)
            return

        cost = car["price"] // 2 if level == 1 else car["price"]
        if user["balance"] < cost:
            answer_callback(callback_id, f"❌ Нужно {cost:,} МШ", alert=True)
            return

        cur.execute("UPDATE users SET balance = balance - %s WHERE telegram_id = %s", (cost, chat_id))
        cur.execute("UPDATE user_cars SET level = level + 1 WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
        conn.commit()

    answer_callback(callback_id, f"⚡ Улучшено до Ур.{level+1}!")
    send(chat_id, f"⚡ <b>{car['emoji']} {car['name']}</b> улучшен до <b>Ур.{level+1}</b>!\n💰 Списано: <b>{cost:,} МШ</b>")


def cb_repair(conn, chat_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, chat_id)
    car = CARS.get(car_id)

    if user["balance"] < 500:
        answer_callback(callback_id, "❌ Нужно 500 МШ для ремонта!", alert=True)
        return

    with conn.cursor() as cur:
        cur.execute("UPDATE users SET balance = balance - 500 WHERE telegram_id = %s", (chat_id,))
        cur.execute("UPDATE user_cars SET broken = FALSE WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
        conn.commit()

    answer_callback(callback_id, "🔧 Отремонтировано!")
    send(chat_id, f"🔧 <b>{car['emoji']} {car['name']}</b> отремонтирован!\n💰 Списано: <b>500 МШ</b>")


def cb_hunt(conn, chat_id: int, car_id: int, callback_id: str):
    with conn.cursor() as cur:
        cur.execute("SELECT level, broken FROM user_cars WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
        row = cur.fetchone()
        if not row or row[1]:
            answer_callback(callback_id, "⚠️ Машина недоступна!", alert=True)
            return
        level = row[0]

    car = CARS[car_id]
    ef = random.randint(1, 5)
    ef_info = EF_DATA[ef]

    level_bonus = (level - 1) * 10
    success_chance = ef_info["chance"] + level_bonus
    roll = random.random() * 100
    success = roll < success_chance
    broken = not success and roll > 85

    answer_callback(callback_id)

    ef_labels = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "💀"}
    label = ef_labels[ef]

    if success:
        reward = ef_info["reward"] + (level - 1) * (ef_info["reward"] // 5)
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET balance = balance + %s WHERE telegram_id = %s", (reward, chat_id))
            conn.commit()

        msgs = [
            "Чисто перехвачен! Данные записаны.",
            "Циклон взят под контроль! Великолепно!",
            "Мощный смерч задокументирован! Легенда!",
            "EF4 покорён! Твоё имя войдёт в историю!",
            "НЕВОЗМОЖНОЕ ВОЗМОЖНО! EF5 перехвачен!!!",
        ]
        send(chat_id,
            f"✅ <b>УСПЕХ!</b>\n\n"
            f"{label} Торнадо <b>{ef_info['name']}</b> · {ef_info['wind']}\n"
            f"{car['emoji']} <b>{car['name']}</b> Ур.{level}\n\n"
            f"<i>{msgs[ef-1]}</i>\n\n"
            f"💰 Награда: <b>+{reward:,} МШ</b>"
        )
    elif broken:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_cars SET broken = TRUE WHERE telegram_id = %s AND car_id = %s", (chat_id, car_id))
            conn.commit()

        msgs = [
            "Небольшой ущерб от обломков. Ремонт нужен.",
            "Боковой удар! Машина повреждена.",
            "Смерч задел борт! Серьёзный ущерб.",
            "EF4 смял крышу! Экипаж цел, машина нет.",
            "EF5 разнёс перехватчик. Чудо что живы.",
        ]
        send(chat_id,
            f"🔴 <b>МАШИНА РАЗБИТА!</b>\n\n"
            f"{label} Торнадо <b>{ef_info['name']}</b> · {ef_info['wind']}\n"
            f"{car['emoji']} <b>{car['name']}</b> — требует ремонта!\n\n"
            f"<i>{msgs[ef-1]}</i>\n\n"
            f"🔧 Ремонт: 500 МШ в /shop"
        )
    else:
        msgs = [
            "Торнадо сменил курс. Промах.",
            "Слишком быстро. Не догнал.",
            "Опасно близко... но ушёл.",
            "EF4 не щадит слабаков. Отступление.",
            "EF5 разбросал всё на пути. Живой — уже победа.",
        ]
        send(chat_id,
            f"❌ <b>ПРОВАЛ</b>\n\n"
            f"{label} Торнадо <b>{ef_info['name']}</b> · {ef_info['wind']}\n"
            f"{car['emoji']} <b>{car['name']}</b> Ур.{level}\n\n"
            f"<i>{msgs[ef-1]}</i>\n\n"
            f"Попробуй снова: /storm"
        )


# ─── ГЛАВНЫЙ ОБРАБОТЧИК ───

def handler(event: dict, context) -> dict:
    """Обработчик webhook от Telegram для бота «Шторм»."""
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    raw_body = event.get("body") or "{}"
    if isinstance(raw_body, dict):
        body = raw_body
    else:
        try:
            body = json.loads(str(raw_body))
        except Exception:
            body = {}
    if not isinstance(body, dict):
        body = {}
    conn = get_db()

    try:
        # Callback query (кнопки)
        if "callback_query" in body:
            cq = body["callback_query"]
            chat_id = cq["from"]["id"]
            callback_id = cq["id"]
            data = cq.get("data", "")

            if data == "boost":
                cb_boost(conn, chat_id, callback_id)
            elif data.startswith("buy_"):
                cb_buy(conn, chat_id, int(data[4:]), callback_id)
            elif data.startswith("shop_"):
                answer_callback(callback_id)
                cmd_shop(conn, chat_id, int(data[5:]))
            elif data.startswith("upgrade_"):
                cb_upgrade(conn, chat_id, int(data[8:]), callback_id)
            elif data.startswith("repair_"):
                cb_repair(conn, chat_id, int(data[7:]), callback_id)
            elif data.startswith("hunt_"):
                cb_hunt(conn, chat_id, int(data[5:]), callback_id)

            return {"statusCode": 200, "headers": CORS, "body": "ok"}

        # Обычное сообщение
        msg = body.get("message", {})
        if not msg:
            return {"statusCode": 200, "headers": CORS, "body": "ok"}

        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        first_name = msg.get("from", {}).get("first_name", "Охотник")

        if text.startswith("/start"):
            cmd_start(conn, chat_id, first_name)
        elif text.startswith("/name "):
            cmd_name(conn, chat_id, text[6:])
        elif text.startswith("/profil"):
            cmd_profil(conn, chat_id)
        elif text.startswith("/shop"):
            cmd_shop(conn, chat_id, 0)
            cmd_shop_upgrade(conn, chat_id)
        elif text.startswith("/storm"):
            cmd_storm(conn, chat_id)
        else:
            send(chat_id,
                "🌪️ Команды:\n"
                "/start — начало\n"
                "/profil — профиль\n"
                "/shop — магазин\n"
                "/storm — охота\n"
                "/name Имя — сменить имя"
            )

    finally:
        conn.close()

    return {"statusCode": 200, "headers": CORS, "body": "ok"}