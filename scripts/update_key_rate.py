#!/usr/bin/env python3
"""Обновляет key-rate.json — историю ключевой ставки Банка России.

Сайт ЦБ не отдаёт CORS-заголовки, поэтому браузер не может читать cbr.ru напрямую.
Страница берёт ставку из key-rate.json со своего же домена (а если файла нет —
из истории, вшитой в index.html). На GitHub Pages скрипт запускает
.github/workflows/update-key-rate.yml по расписанию.

Без аргументов пишет key-rate.json в корень сайта (на уровень выше scripts/);
можно передать путь к файлу. Только стандартная библиотека Python 3.8+.
"""
import json, os, re, sys, tempfile, time, urllib.request
from datetime import date, datetime, timedelta, timezone

URL = ("https://www.cbr.ru/hd_base/KeyRate/?UniDbQuery.Posted=True"
       "&UniDbQuery.From=17.09.2013&UniDbQuery.To={to}")


def fetch_history():
    msk = datetime.now(timezone(timedelta(hours=3))).date()
    req = urllib.request.Request(URL.format(to=(msk + timedelta(days=7)).strftime("%d.%m.%Y")),
                                 headers={"User-Agent": "impravo-key-rate/1.0"})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                page = r.read().decode("utf-8")
            break
        except Exception as exc:  # сеть/таймаут/5xx — пробуем ещё раз
            if attempt == 3:
                raise
            print(f"Попытка {attempt} не удалась: {exc}; повтор через {attempt * 20} с", file=sys.stderr)
            time.sleep(attempt * 20)
    rows = re.findall(r"<td>(\d\d)\.(\d\d)\.(\d{4})</td>\s*<td>([\d,]+)</td>", page)
    points = sorted((f"{y}-{m}-{d}", float(v.replace(",", "."))) for d, m, y, v in rows)
    if len(points) < 100:
        raise RuntimeError(f"ЦБ вернул подозрительно мало строк: {len(points)}")
    history, prev = [], None
    for day, value in points:
        if not 0 < value < 100:
            raise RuntimeError(f"Некорректная ставка {value} на {day}")
        if value != prev:
            history.append([day, value])
            prev = value
    return {"updated": points[-1][0], "source": "https://www.cbr.ru/hd_base/KeyRate/", "history": history}


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "key-rate.json")
    data = fetch_history()
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(target)), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.chmod(tmp, 0o644)
    os.replace(tmp, target)  # атомарная замена: сайт не увидит полузаписанный файл
    last = data["history"][-1]
    print(f"OK: {last[1]}% с {last[0]}, данные на {data['updated']} -> {target}")


if __name__ == "__main__":
    main()
