#!/usr/bin/env python3
"""
Скрапер материалов EGGER (Австрия) с profikz.kz.

Собираем два раздела:
  • ЛДСП/ЛМДФ EGGER — несколько подкатегорий-страниц каталога, все они
    сводятся в ОДНУ категорию приложения "ЛДСП: Австрия (Egger)".
  • Столешницы EGGER — категория "Столешницы: Австрия (Egger)".

profikz.kz работает на том же движке (1С-Битрикс), что и em-c.kz, поэтому
разметка карточек товара идентична: ссылка-заголовок с классом
js-notice-block__title, пагинация через ?PAGEN_1=N. Благодаря этому парсинг
почти повторяет scraper/scrape.py, но вынесен в отдельный модуль, чтобы
источники не путались и падение одного не роняло остальные.

Фото в списке отдаются в виде уменьшенной копии из resize_cache
(/upload/resize_cache/iblock/AAA/600_600_HASH/FILE) — мы приводим ссылку к
ОРИГИНАЛУ (/upload/iblock/AAA/FILE), чтобы image_utils сам сжал её в нужные
размеры без потери качества из-за двойного ресайза.
"""

import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://profikz.kz"

# Подкатегории ЛДСП/ЛМДФ EGGER — все ведут в одну категорию приложения.
LDSP_PATHS = [
    "/catalog/egger/listovye_materialy/ldsp_lmdf_egger/",
    "/catalog/egger/listovye_materialy/ldsp_egger_u/",
    "/catalog/egger/listovye_materialy/ldsp_egger_1_2/",
    "/catalog/egger/listovye_materialy/ldsp_lmdf_egger_perfectsense_lakirovannye_plity_/",
]
LDSP_CATEGORY = "ЛДСП: Австрия (Egger)"

STOL_PATHS = [
    "/catalog/egger/stoleshnitsy_i_mebelnye_shchity_1/stoleshnitsy_egger/",
]
STOL_CATEGORY = "Столешницы: Австрия (Egger)"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

PAGEN_RE = re.compile(r"PAGEN_1=(\d+)")
# /upload/resize_cache/iblock/AAA/600_600_HASH/FILE.ext -> iblock/AAA, FILE.ext
RESIZE_RE = re.compile(r"/upload/resize_cache/(iblock/[0-9a-f]+)/[^/]+/([^/?#]+)")


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    return resp.text


def full_image_url(src: str | None) -> str | None:
    """Приводит ссылку на фото к абсолютному оригиналу (без resize_cache)."""
    if not src:
        return None
    if src.startswith("//"):
        src = "https:" + src
    m = RESIZE_RE.search(src)
    if m:
        src = "/upload/" + m.group(1) + "/" + m.group(2)
    if src.startswith("/"):
        src = BASE_URL + src
    return src


def _card_image(anchor) -> str | None:
    """Ищет фото товара в ближайшем контейнере-карточке вокруг заголовка."""
    node = anchor
    for _ in range(10):
        node = node.parent
        if node is None:
            break
        classes = node.get("class") or []
        if any(c in ("item", "catalog_item", "product-item", "list_item") for c in classes):
            for img in node.select("img"):
                s = img.get("data-src") or img.get("src")
                if s and ("resize_cache" in s or "/upload/iblock" in s):
                    return s
            break
    return None


def parse_listing(html: str, category_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for a in soup.select("a.js-notice-block__title"):
        href = a.get("href")
        if not href:
            continue
        name = a.get_text(strip=True)

        # id — числовой идентификатор элемента из URL (у Битрикса глобально
        # уникален), с префиксом источника для маршрутизации фото/чистки сирот.
        m = re.search(r"/(\d+)/?$", href.rstrip("/"))
        raw_id = m.group(1) if m else href.strip("/").replace("/", "_")
        item_id = "profikz_" + raw_id

        img_src = full_image_url(_card_image(a))

        items.append(
            {
                "id": item_id,
                "name": name,
                "category": category_name,
                "url": (BASE_URL + href) if href.startswith("/") else href,
                "image": img_src,
                "images": [img_src] if img_src else [],
            }
        )
    return items


def max_page_number(html: str) -> int:
    return max([1, *[int(n) for n in PAGEN_RE.findall(html)]])


def scrape_section(path: str, category_name: str) -> list[dict]:
    first_html = fetch(BASE_URL + path)
    total_pages = max_page_number(first_html)
    results = parse_listing(first_html, category_name)
    for page in range(2, total_pages + 1):
        time.sleep(0.4)  # вежливая пауза между запросами
        html = fetch(f"{BASE_URL}{path}?PAGEN_1={page}")
        results.extend(parse_listing(html, category_name))
    return results


def scrape_all() -> list[dict]:
    results: list[dict] = []

    for path in LDSP_PATHS:
        try:
            items = scrape_section(path, LDSP_CATEGORY)
            print(f"[scrape_profikz] {path}: {len(items)} позиций", file=sys.stderr)
            results.extend(items)
        except requests.RequestException as exc:
            print(f"[scrape_profikz] ошибка на {path}: {exc}", file=sys.stderr)

    for path in STOL_PATHS:
        try:
            items = scrape_section(path, STOL_CATEGORY)
            print(f"[scrape_profikz] {path}: {len(items)} позиций", file=sys.stderr)
            results.extend(items)
        except requests.RequestException as exc:
            print(f"[scrape_profikz] ошибка на {path}: {exc}", file=sys.stderr)

    # Подкатегории ЛДСП могут пересекаться по товарам — дедуп по id.
    seen: dict[str, dict] = {}
    for item in results:
        seen[item["id"]] = item
    return list(seen.values())


if __name__ == "__main__":
    # Самостоятельный запуск: печатает JSON в stdout (для отладки).
    items = scrape_all()
    print(json.dumps(items, ensure_ascii=False, indent=2))
