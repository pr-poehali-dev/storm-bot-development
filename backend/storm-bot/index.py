"""
Telegram-бот «Шторм» — обработчик webhook-запросов от Telegram.
Поддерживает личные сообщения и группы.
"""
import json
import os
import re
import random
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

EF_LABELS = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "💀"}

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

HELP_TEXT = (
    "🌪️ <b>ШТОРМ — Охотники за торнадо</b>\n\n"
    "<b>Команды:</b>\n"
    "/start — приветствие и регистрация\n"
    "/profil — профиль, баланс, гараж\n"
    "/garage — список всех машин в гараже\n"
    "/shop — магазин машин (покупка, улучшение, ремонт)\n"
    "/storm — выехать на охоту за торнадо\n"
    "/balance — быстро проверить баланс\n"
    "/name Имя — сменить игровое имя\n"
    "/help — это сообщение\n\n"
    "<b>Валюта:</b> Магшиормы (МШ)\n"
    "<b>Буст:</b> +200 МШ каждые 20 минут в /profil\n\n"
    "<b>Шкала торнадо:</b>\n"
    "🟢 EF1 — шанс 80%, награда 300 МШ\n"
    "🟡 EF2 — шанс 65%, награда 600 МШ\n"
    "🟠 EF3 — шанс 50%, награда 1 100 МШ\n"
    "🔴 EF4 — шанс 35%, награда 2 000 МШ\n"
    "💀 EF5 — шанс 20%, награда 4 000 МШ\n\n"
    "<i>Удачной охоты, сталкер! 🎯</i>"
)


# ─── УТИЛИТЫ ───

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def parse_command(text: str):
    """
    Парсит команду из текста.
    Поддерживает: /cmd, /cmd@botname, /cmd arg, /cmd@botname arg
    Возвращает (команда_без_@, аргумент)
    """
    if not text or not text.startswith("/"):
        return None, ""
    parts = text.split(None, 1)
    cmd_part = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    # убираем @botname
    cmd = re.sub(r"@\w+$", "", cmd_part)
    return cmd, arg


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


# ─── РАБОТА С БД ───

def get_or_create_user(conn, user_id: int, first_name: str = "Охотник"):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT telegram_id, name, balance, boost_used_at FROM users WHERE telegram_id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        if row:
            return {"telegram_id": row[0], "name": row[1], "balance": row[2], "boost_used_at": row[3]}
        cur.execute(
            "INSERT INTO users (telegram_id, name, balance) VALUES (%s, %s, 5000) "
            "RETURNING telegram_id, name, balance, boost_used_at",
            (user_id, first_name[:20])
        )
        row = cur.fetchone()
        conn.commit()
        return {"telegram_id": row[0], "name": row[1], "balance": row[2], "boost_used_at": row[3]}


def get_user_cars(conn, user_id: int):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT car_id, level, broken FROM user_cars WHERE telegram_id = %s ORDER BY car_id",
            (user_id,)
        )
        return [{"car_id": r[0], "level": r[1], "broken": r[2]} for r in cur.fetchall()]


def boost_status(boost_used_at):
    """Возвращает (can_boost: bool, text: str, remaining_secs: int)"""
    now = datetime.now(timezone.utc)
    if not boost_used_at:
        return True, "✅ Доступен!", 0
    used_at = boost_used_at
    if used_at.tzinfo is None:
        used_at = used_at.replace(tzinfo=timezone.utc)
    delta = now - used_at
    remaining = timedelta(minutes=BOOST_COOLDOWN_MINUTES) - delta
    if remaining.total_seconds() <= 0:
        return True, "✅ Доступен!", 0
    mins = int(remaining.total_seconds() // 60)
    secs = int(remaining.total_seconds() % 60)
    return False, f"⏳ {mins}:{secs:02d}", int(remaining.total_seconds())


# ─── КОМАНДЫ ───

def cmd_start(conn, chat_id: int, user_id: int, first_name: str):
    user = get_or_create_user(conn, user_id, first_name)
    text = (
        "🌪️ <b>ШТОРМ — Охотники за торнадо</b>\n\n"
        f"Добро пожаловать, <b>{user['name']}</b>!\n"
        "Ты — охотник на торнадо. Покупай машины-перехватчики,\n"
        "улучшай их и выезжай на охоту!\n\n"
        f"💰 Стартовый баланс: <b>{user['balance']:,} МШ</b>\n\n"
        "/help — все команды и правила игры"
    )
    send(chat_id, text)


def cmd_help(chat_id: int):
    send(chat_id, HELP_TEXT)


def cmd_balance(conn, chat_id: int, user_id: int, first_name: str):
    user = get_or_create_user(conn, user_id, first_name)
    send(chat_id, f"💰 <b>{user['name']}</b>: <b>{user['balance']:,} МШ</b>")


def cmd_name(conn, chat_id: int, user_id: int, new_name: str):
    new_name = new_name.strip()[:20]
    if not new_name:
        send(chat_id, "⚠️ Укажи имя: <code>/name ТвоёИмя</code>")
        return
    # убеждаемся что пользователь существует
    get_or_create_user(conn, user_id)
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET name = %s WHERE telegram_id = %s", (new_name, user_id))
        conn.commit()
    send(chat_id, f"✅ Имя изменено на <b>{new_name}</b>!")


def cmd_profil(conn, chat_id: int, user_id: int, first_name: str):
    user = get_or_create_user(conn, user_id, first_name)
    cars = get_user_cars(conn, user_id)
    can_boost, boost_text, _ = boost_status(user["boost_used_at"])

    car_lines = ""
    for c in cars[:5]:
        car = CARS[c["car_id"]]
        status = "🔴 сломана" if c["broken"] else f"Ур.{c['level']}"
        car_lines += f"  {car['emoji']} {car['name']} — {status}\n"
    if len(cars) > 5:
        car_lines += f"  ... и ещё {len(cars) - 5} машин\n"
    if not cars:
        car_lines = "  Гараж пуст — купи машину в /shop\n"

    text = (
        f"👤 <b>{user['name']}</b>\n"
        "─────────────────\n"
        f"💰 Баланс: <b>{user['balance']:,} МШ</b>\n"
        f"🚗 Машин в гараже: <b>{len(cars)}</b>\n\n"
        f"🏠 <b>ГАРАЖ:</b>\n{car_lines}\n"
        "─────────────────"
    )

    markup = {"inline_keyboard": [[
        {"text": f"⚡ Буст +200 МШ ({boost_text})", "callback_data": f"boost_{user_id}"},
    ]]}
    send(chat_id, text, reply_markup=markup)


def cmd_garage(conn, chat_id: int, user_id: int, first_name: str):
    """Полный список машин — работает в группах."""
    user = get_or_create_user(conn, user_id, first_name)
    cars = get_user_cars(conn, user_id)

    if not cars:
        send(chat_id, f"🚗 <b>{user['name']}</b>, твой гараж пуст.\nКупи машину в /shop")
        return

    lines = f"🏠 <b>Гараж: {user['name']}</b> ({len(cars)} машин)\n─────────────────\n"
    for c in cars:
        car = CARS[c["car_id"]]
        if c["broken"]:
            status = "🔴 сломана"
        elif c["level"] == 3:
            status = "🟡 Ур.3 МАКС"
        elif c["level"] == 2:
            status = "🔵 Ур.2"
        else:
            status = "🟢 Ур.1"
        lines += f"{car['emoji']} <b>{car['name']}</b> — {status}\n"

    send(chat_id, lines)


def cmd_shop(conn, chat_id: int, user_id: int, first_name: str, page: int = 0):
    cars_list = list(CARS.items())
    per_page = 3
    total_pages = (len(cars_list) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    user = get_or_create_user(conn, user_id, first_name)
    owned = {c["car_id"] for c in get_user_cars(conn, user_id)}

    text = f"🔧 <b>МАГАЗИН ПЕРЕХВАТЧИКОВ</b> (стр. {page + 1}/{total_pages})\n"
    text += f"💰 Твой баланс: <b>{user['balance']:,} МШ</b>\n"
    text += "─────────────────\n"

    buttons = []
    for car_id, car in cars_list[page * per_page:(page + 1) * per_page]:
        if car_id in owned:
            text += f"✅ {car['emoji']} <b>{car['name']}</b> — в гараже\n"
        else:
            text += f"🔒 {car['emoji']} <b>{car['name']}</b> — {car['price']:,} МШ\n"
            buttons.append([{
                "text": f"Купить {car['emoji']} {car['name']} ({car['price']:,} МШ)",
                "callback_data": f"buy_{user_id}_{car_id}"
            }])

    nav = []
    if page > 0:
        nav.append({"text": "◀️ Назад", "callback_data": f"shop_{user_id}_{page - 1}"})
    if page < total_pages - 1:
        nav.append({"text": "Вперёд ▶️", "callback_data": f"shop_{user_id}_{page + 1}"})
    if nav:
        buttons.append(nav)

    markup = {"inline_keyboard": buttons} if buttons else None
    send(chat_id, text, reply_markup=markup)

    # Показываем улучшения/ремонт отдельным сообщением
    cmd_shop_upgrade(conn, chat_id, user_id)


def cmd_shop_upgrade(conn, chat_id: int, user_id: int):
    user = get_or_create_user(conn, user_id)
    user_cars = get_user_cars(conn, user_id)
    upgradeable = [c for c in user_cars if c["level"] < 3 and not c["broken"]]
    broken_cars = [c for c in user_cars if c["broken"]]

    if not upgradeable and not broken_cars:
        return

    text = f"⚙️ <b>УЛУЧШЕНИЯ И РЕМОНТ</b>\n💰 Баланс: <b>{user['balance']:,} МШ</b>\n─────────────────\n"
    buttons = []

    for c in upgradeable:
        car = CARS[c["car_id"]]
        cost = car["price"] // 2 if c["level"] == 1 else car["price"]
        text += f"⚡ {car['emoji']} {car['name']} Ур.{c['level']}→{c['level'] + 1}: {cost:,} МШ\n"
        buttons.append([{
            "text": f"⚡ {car['name']} Ур.{c['level']}→{c['level'] + 1} ({cost:,} МШ)",
            "callback_data": f"upgrade_{user_id}_{c['car_id']}"
        }])

    for c in broken_cars:
        car = CARS[c["car_id"]]
        text += f"🔴 {car['emoji']} {car['name']} — сломана (ремонт 500 МШ)\n"
        buttons.append([{
            "text": f"🔧 Починить {car['name']} (500 МШ)",
            "callback_data": f"repair_{user_id}_{c['car_id']}"
        }])

    send(chat_id, text, reply_markup={"inline_keyboard": buttons})


def cmd_storm(conn, chat_id: int, user_id: int, first_name: str):
    get_or_create_user(conn, user_id, first_name)
    user_cars = get_user_cars(conn, user_id)
    ready = [c for c in user_cars if not c["broken"]]

    if not ready:
        send(chat_id, "🚗 Нет готовых машин для охоты!\nКупи в /shop или почини сломанную.")
        return

    text = "🌪️ <b>ОХОТА НА ТОРНАДО</b>\nВыбери машину-перехватчик:\n─────────────────\n"
    buttons = []
    for c in ready:
        car = CARS[c["car_id"]]
        bonus = (c["level"] - 1) * 10
        bonus_text = f" (+{bonus}%)" if bonus else ""
        text += f"{car['emoji']} <b>{car['name']}</b> Ур.{c['level']}{bonus_text}\n"
        buttons.append([{
            "text": f"{car['emoji']} {car['name']} Ур.{c['level']}{bonus_text}",
            "callback_data": f"hunt_{user_id}_{c['car_id']}"
        }])

    text += "\n<i>Шанс успеха зависит от уровня машины и категории торнадо</i>"
    send(chat_id, text, reply_markup={"inline_keyboard": buttons})


# ─── CALLBACK ОБРАБОТЧИКИ ───
# Все callback_data теперь содержат user_id: "action_userid_param"
# Это позволяет правильно работать в группах

def cb_boost(conn, chat_id: int, user_id: int, callback_id: str):
    user = get_or_create_user(conn, user_id)
    can_boost, boost_text, _ = boost_status(user["boost_used_at"])

    if not can_boost:
        answer_callback(callback_id, f"⏳ Буст будет через {boost_text.replace('⏳ ', '')}", alert=True)
        return

    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET balance = balance + 200, boost_used_at = %s WHERE telegram_id = %s",
            (now, user_id)
        )
        conn.commit()

    answer_callback(callback_id, "⚡ +200 МШ получено!")
    send(chat_id,
         f"⚡ <b>Буст активирован!</b>\n"
         f"<b>{user['name']}</b> получает +200 МШ!\n"
         f"Следующий буст через {BOOST_COOLDOWN_MINUTES} минут."
    )


def cb_buy(conn, chat_id: int, user_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, user_id)
    car = CARS.get(car_id)
    if not car:
        answer_callback(callback_id, "Ошибка: машина не найдена", alert=True)
        return

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM user_cars WHERE telegram_id = %s AND car_id = %s",
            (user_id, car_id)
        )
        if cur.fetchone():
            answer_callback(callback_id, "⚠️ Уже в гараже!", alert=True)
            return

        if user["balance"] < car["price"]:
            answer_callback(callback_id, f"❌ Недостаточно МШ! Нужно {car['price']:,}", alert=True)
            return

        cur.execute("UPDATE users SET balance = balance - %s WHERE telegram_id = %s", (car["price"], user_id))
        cur.execute(
            "INSERT INTO user_cars (telegram_id, car_id, level, broken) VALUES (%s, %s, 1, FALSE)",
            (user_id, car_id)
        )
        conn.commit()

    answer_callback(callback_id, f"✅ {car['name']} куплен!")
    send(chat_id,
         f"✅ <b>{car['emoji']} {car['name']}</b> добавлен в гараж <b>{user['name']}</b>!\n"
         f"💰 Списано: <b>{car['price']:,} МШ</b>"
    )


def cb_upgrade(conn, chat_id: int, user_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, user_id)
    car = CARS.get(car_id)
    if not car:
        answer_callback(callback_id, "Машина не найдена", alert=True)
        return

    with conn.cursor() as cur:
        cur.execute(
            "SELECT level, broken FROM user_cars WHERE telegram_id = %s AND car_id = %s",
            (user_id, car_id)
        )
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

        cur.execute("UPDATE users SET balance = balance - %s WHERE telegram_id = %s", (cost, user_id))
        cur.execute(
            "UPDATE user_cars SET level = level + 1 WHERE telegram_id = %s AND car_id = %s",
            (user_id, car_id)
        )
        conn.commit()

    answer_callback(callback_id, f"⚡ Улучшено до Ур.{level + 1}!")
    send(chat_id,
         f"⚡ <b>{car['emoji']} {car['name']}</b> улучшен до <b>Ур.{level + 1}</b>!\n"
         f"💰 Списано: <b>{cost:,} МШ</b>"
    )


def cb_repair(conn, chat_id: int, user_id: int, car_id: int, callback_id: str):
    user = get_or_create_user(conn, user_id)
    car = CARS.get(car_id)
    if not car:
        answer_callback(callback_id, "Машина не найдена", alert=True)
        return

    if user["balance"] < 500:
        answer_callback(callback_id, "❌ Нужно 500 МШ для ремонта!", alert=True)
        return

    with conn.cursor() as cur:
        cur.execute("UPDATE users SET balance = balance - 500 WHERE telegram_id = %s", (user_id,))
        cur.execute(
            "UPDATE user_cars SET broken = FALSE WHERE telegram_id = %s AND car_id = %s",
            (user_id, car_id)
        )
        conn.commit()

    answer_callback(callback_id, "🔧 Отремонтировано!")
    send(chat_id,
         f"🔧 <b>{car['emoji']} {car['name']}</b> отремонтирован!\n"
         f"💰 Списано: <b>500 МШ</b>"
    )


def cb_hunt(conn, chat_id: int, user_id: int, car_id: int, callback_id: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT level, broken FROM user_cars WHERE telegram_id = %s AND car_id = %s",
            (user_id, car_id)
        )
        row = cur.fetchone()
        if not row or row[1]:
            answer_callback(callback_id, "⚠️ Машина недоступна!", alert=True)
            return
        level = row[0]

    car = CARS[car_id]
    ef = random.randint(1, 5)
    ef_info = EF_DATA[ef]
    label = EF_LABELS[ef]

    success_chance = ef_info["chance"] + (level - 1) * 10
    roll = random.random() * 100
    success = roll < success_chance
    broken = not success and roll > 85

    answer_callback(callback_id)

    with conn.cursor() as cur:
        if success:
            reward = ef_info["reward"] + (level - 1) * (ef_info["reward"] // 5)
            cur.execute("UPDATE users SET balance = balance + %s WHERE telegram_id = %s", (reward, user_id))
            conn.commit()

            success_msgs = [
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
                f"<i>{success_msgs[ef - 1]}</i>\n\n"
                f"💰 Награда: <b>+{reward:,} МШ</b>"
            )
        elif broken:
            cur.execute(
                "UPDATE user_cars SET broken = TRUE WHERE telegram_id = %s AND car_id = %s",
                (user_id, car_id)
            )
            conn.commit()

            break_msgs = [
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
                f"<i>{break_msgs[ef - 1]}</i>\n\n"
                f"🔧 Ремонт: 500 МШ — /shop"
            )
        else:
            fail_msgs = [
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
                f"<i>{fail_msgs[ef - 1]}</i>\n\n"
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
        # ── Callback query (кнопки) ──
        if "callback_query" in body:
            cq = body["callback_query"]
            # В группах кнопку может нажать ЛЮБОЙ юзер.
            # Все callback_data содержат owner_user_id: "action_ownerid_param"
            # Проверяем что нажал именно владелец кнопки.
            presser_id = cq["from"]["id"]
            chat_id = cq["message"]["chat"]["id"]
            callback_id = cq["id"]
            data = cq.get("data", "")
            parts = data.split("_")

            if data.startswith("boost_") and len(parts) == 2:
                owner_id = int(parts[1])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    cb_boost(conn, chat_id, owner_id, callback_id)

            elif data.startswith("buy_") and len(parts) == 3:
                owner_id = int(parts[1])
                car_id = int(parts[2])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    cb_buy(conn, chat_id, owner_id, car_id, callback_id)

            elif data.startswith("shop_") and len(parts) == 3:
                owner_id = int(parts[1])
                page = int(parts[2])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    answer_callback(callback_id)
                    cmd_shop(conn, chat_id, owner_id, "", page)

            elif data.startswith("upgrade_") and len(parts) == 3:
                owner_id = int(parts[1])
                car_id = int(parts[2])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    cb_upgrade(conn, chat_id, owner_id, car_id, callback_id)

            elif data.startswith("repair_") and len(parts) == 3:
                owner_id = int(parts[1])
                car_id = int(parts[2])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    cb_repair(conn, chat_id, owner_id, car_id, callback_id)

            elif data.startswith("hunt_") and len(parts) == 3:
                owner_id = int(parts[1])
                car_id = int(parts[2])
                if presser_id != owner_id:
                    answer_callback(callback_id, "⚠️ Это чужая кнопка!", alert=True)
                else:
                    cb_hunt(conn, chat_id, owner_id, car_id, callback_id)

            else:
                answer_callback(callback_id)

            return {"statusCode": 200, "headers": CORS, "body": "ok"}

        # ── Обычное сообщение ──
        msg = body.get("message", {})
        if not msg:
            return {"statusCode": 200, "headers": CORS, "body": "ok"}

        chat_id = msg["chat"]["id"]
        # ВАЖНО: user_id всегда берём из "from", а не из "chat"
        user_id = msg["from"]["id"]
        first_name = msg["from"].get("first_name", "Охотник")
        text = msg.get("text", "") or ""

        cmd, arg = parse_command(text)

        if cmd == "/start":
            cmd_start(conn, chat_id, user_id, first_name)
        elif cmd == "/help":
            cmd_help(chat_id)
        elif cmd == "/name":
            cmd_name(conn, chat_id, user_id, arg)
        elif cmd == "/profil":
            cmd_profil(conn, chat_id, user_id, first_name)
        elif cmd == "/garage":
            cmd_garage(conn, chat_id, user_id, first_name)
        elif cmd == "/balance":
            cmd_balance(conn, chat_id, user_id, first_name)
        elif cmd == "/shop":
            cmd_shop(conn, chat_id, user_id, first_name, 0)
        elif cmd == "/storm":
            cmd_storm(conn, chat_id, user_id, first_name)
        elif text and text.startswith("/"):
            # Неизвестная команда — только в личке, не спамить в группах
            if msg["chat"]["type"] == "private":
                send(chat_id, "❓ Неизвестная команда. /help — список команд")

    finally:
        conn.close()

    return {"statusCode": 200, "headers": CORS, "body": "ok"}
