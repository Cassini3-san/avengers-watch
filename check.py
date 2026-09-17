#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py — одна проверка API cinematica.uz. Запускается GitHub Actions по
расписанию. Состояние между запусками не хранится: условие тревоги абсолютное —
"есть хотя бы один сеанс, доступный к покупке".

Переменные окружения:
    TG_TOKEN   — токен Telegram-бота
    TG_CHAT    — chat_id получателя
    WATCH_URL  — адрес API (по умолчанию репертуар фильма 995)
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

URL = os.environ.get(
    "WATCH_URL",
    "https://cinematica.uz/api/v1/repertory/movie/995/grouped",
)
PAGE = os.environ.get("WATCH_PAGE", "https://cinematica.uz/movies/995")
TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]

TASHKENT = timezone(timedelta(hours=5))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def send(text):
    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode()
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % TOKEN, data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def fetch():
    req = urllib.request.Request(URL, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def main():
    now = datetime.now(TASHKENT)

    try:
        data = fetch()
    except Exception as exc:
        # Одиночный сбой сети не повод будить человека — просто валим запуск,
        # GitHub покажет красный крестик в истории.
        print("Ошибка запроса: %s" % exc)
        sys.exit(1)

    rows = data.get("list") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []

    sellable = [r for r in rows
                if isinstance(r, dict) and r.get("disable_sales") is False]

    print("%s — всего записей: %d, к покупке: %d"
          % (now.strftime("%Y-%m-%d %H:%M"), len(rows), len(sellable)))

    if sellable:
        # Собираем краткую сводку: зал, дата, время, цена
        lines = []
        for r in sellable[:15]:
            lines.append("• %s | %s %s | %s сум" % (
                r.get("hall") or r.get("cinema") or "?",
                r.get("date") or "",
                r.get("time") or "",
                ("%.0f" % r["price"]) if isinstance(r.get("price"), (int, float)) else "?",
            ))
        imax = [l for l in lines if "IMAX" in l.upper()]
        send(
            "🔥 ПРОДАЖИ ОТКРЫТЫ!\n"
            "Доступно к покупке сеансов: %d%s\n\n%s\n\n%s"
            % (
                len(sellable),
                (" (из них IMAX: %d)" % len(imax)) if imax else "",
                "\n".join(lines[:15]),
                PAGE,
            )
        )
        print("Уведомление отправлено.")
        return

    if rows:
        send(
            "📅 Появилось расписание: %d сеансов, но покупка ещё закрыта.\n"
            "Продажи вот-вот откроются — держите телефон рядом.\n\n%s"
            % (len(rows), PAGE)
        )
        print("Расписание появилось, продажи закрыты.")
        return

    # Раз в сутки, в 09:00 по Ташкенту, подтверждаем что слежение живо.
    if now.hour == 9 and now.minute < 10:
        send("🟢 Слежение работает. Сеансов пока нет.")
        print("Отправлен heartbeat.")


if __name__ == "__main__":
    main()
