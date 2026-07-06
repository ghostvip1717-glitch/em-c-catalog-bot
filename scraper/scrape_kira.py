#!/usr/bin/env python3
"""
Скрапер плёнки ПВХ с kira-group.kz (https://kira-group.kz/catalogpvh).

Особенность этого сайта: он сделан на конструкторе Tilda с блоком
"Tilda Store" — список товаров рендерится JS-виджетом (tilda-catalog,
tilda-products) уже ПОСЛЕ загрузки страницы, из отдельного бэкенда
store.tildaapi.pro, а не лежит в исходном HTML. Простой GET на
kira-group.kz/catalogpvh отдаёт только форму заявки — товаров там нет.

Зато сам бэкенд store.tildaapi.pro отдаёт чистый JSON без авторизации и без
капчи — можно обойтись requests'ом, не поднимая headless-браузер:

    GET https://store.tildaapi.pro/api/getproductslist/
        ?storepartuid=<ID магазина на сайте>
        &recid=<ID товарного блока на странице>
        &getparts=true&getoptions=true
        &slice=<номер страницы, с 1>&size=<кол-во на страницу>

В ответе сразу лежат все нужные поля: title (название), gallery (JSON-строка
со списком фото), url (страница товара на kira-group.kz). Поле "brand" у
этого магазина используется как фильтр "По покрытию" (значения
"Глянец"/"Матовое") — удобно, чтобы разложить товары на две подкатегории,
а не свалить все ~97 позиций в одну "ПВХ плёнка: KIRA". Пагинация — по полю
"total" (сколько всего товаров) и "nextslice"; идём, пока не наберём total
или пока products не пустой (проверено вручную: slice=5 из 5 отдаёт последний
остаток без поля nextslice).

STOREPARTUID/RECID — фиксированные ID конкретного товарного блока на
конкретной странице сайта, увидены через вкладку Network в браузере на
https://kira-group.kz/catalogpvh. Если Kira когда-нибудь пересоберёт эту
страницу заново в Tilda-редакторе, ID могут поменяться — тогда скрипт начнёт
получать пустой список, и это будет видно в логе.

Префикс "ПВХ плёнка" в названии категории (как и у adilet.net) нужен
фронтенду (index.html, siteGroupOf) для группировки под общую иконку
"Плёнка" в приложении — см. комментарии там же.
"""

import json
import sys
import time

import requests

API_URL = "https://store.tildaapi.pro/api/getproductslist/"
STOREPARTUID = "793696220374"
RECID = "1493222651"
PAGE_SIZE = 24

# "brand" в ответе API — это фильтр "По покрытию" на сайте (не бренд плёнки).
# Используем его, чтобы разложить товары по двум подкатегориям.
BRAND_TO_CATEGORY = {
    "Глянец": "ПВХ плёнка: KIRA Глянец",
    "Матовое": "ПВХ плёнка: KIRA Матовое",
}
DEFAULT_CATEGORY = "ПВХ плёнка: KIRA"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_slice(slice_num: int) -> dict:
    params = {
        "storepartuid": STOREPARTUID,
        "recid": RECID,
        "getparts": "true",
        "getoptions": "true",
        "slice": slice_num,
        "size": PAGE_SIZE,
        "flag_root": "withroot",
    }
    resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def parse_product(product: dict) -> dict | None:
    name = (product.get("title") or "").strip()
    if not name:
        return None

    try:
        gallery = json.loads(product.get("gallery") or "[]")
    except (TypeError, ValueError):
        gallery = []
    images = [g["img"] for g in gallery if isinstance(g, dict) and g.get("img")]

    category = BRAND_TO_CATEGORY.get(product.get("brand"), DEFAULT_CATEGORY)

    return {
        "id": "kira_" + str(product.get("uid")),
        "name": name,
        "category": category,
        "url": product.get("url") or "",
        "image": images[0] if images else None,
        "images": images,
    }


def scrape_all() -> list[dict]:
    results: list[dict] = []
    slice_num = 1
    total = None

    while True:
        try:
            data = fetch_slice(slice_num)
        except requests.RequestException as exc:
            print(f"[scrape_kira] ошибка на странице {slice_num}: {exc}", file=sys.stderr)
            break

        if total is None:
            total = data.get("total")
            print(f"[scrape_kira] всего товаров по данным API: {total}", file=sys.stderr)

        products = data.get("products") or []
        if not products:
            break

        for product in products:
            item = parse_product(product)
            if item:
                results.append(item)

        if not data.get("nextslice") or (total is not None and len(results) >= total):
            break
        slice_num = data["nextslice"]
        time.sleep(0.3)  # вежливая пауза между запросами

    return results


if __name__ == "__main__":
    # Самостоятельный запуск: печатает JSON в stdout (для отладки).
    items = scrape_all()
    print(json.dumps(items, ensure_ascii=False, indent=2))
