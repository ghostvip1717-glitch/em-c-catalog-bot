#!/usr/bin/env python3
"""
Скрапер каталога "Листовые материалы" с em-c.kz.
Собирает: id (slug), название, категорию, ссылку на карточку товара и фото.
Цена и остатки намеренно НЕ собираются — приложению они не нужны.

Запускается вручную (python scrape.py) или по расписанию через GitHub Actions
(см. .github/workflows/update-catalog.yml).
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import image_utils
import scrape_adilet
import scrape_interstone
import scrape_kira
import scrape_profikz

BASE_URL = "https://www.em-c.kz"

# slug раздела em-c.kz -> человекочитаемое название категории.
# Берём российские ЛДСП и столешницы. Суффикс ": Россия" в названии нужен,
# чтобы фронтенд мог отделить их от австрийских (Egger) аналогов с profikz.kz
# (см. scrape_profikz.py и siteGroupOf в index.html). Остальные разделы em-c
# (ДВП, ДСП, МДФ, фанера, ХДФ и т.п.) в каталоге не нужны.
CATEGORIES = {
    "ldsp": "ЛДСП: Россия",
    "stoleshnitsy": "Столешницы: Россия",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "materials.json"

PAGEN_RE = re.compile(r"PAGEN_1=(\d+)")


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def site_of(item_id: str) -> str:
    """Источник товара по префиксу его id — определяет папку в data/images/."""
    for prefix, site in (
        ("adilet_", "adilet"),
        ("interstone_", "interstone"),
        ("kira_", "kira"),
        ("profikz_", "profikz"),
    ):
        if item_id.startswith(prefix):
            return site
    return "emc"


def parse_category_page(html: str, category_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for link in soup.select("a.js-notice-block__title"):
        href = link.get("href")
        if not href:
            continue
        name = link.get_text(strip=True)

        card = link.find_parent("div", class_="item")
        img_src = None
        if card:
            img = card.find("img")
            if img:
                img_src = img.get("src") or img.get("data-src")

        item_id = href.strip("/")
        if item_id.startswith("catalog/"):
            item_id = item_id[len("catalog/"):]
        if item_id.endswith(".html"):
            item_id = item_id[: -len(".html")]

        items.append(
            {
                "id": item_id,
                "name": name,
                "category": category_name,
                "url": BASE_URL + href,
                "image": (BASE_URL + img_src) if img_src and img_src.startswith("/") else img_src,
            }
        )
    return items


def max_page_number(html: str) -> int:
    return max([1, *[int(n) for n in PAGEN_RE.findall(html)]])


def scrape_category(slug: str, category_name: str) -> list[dict]:
    first_url = f"{BASE_URL}/catalog/{slug}/"
    first_html = fetch(first_url)
    total_pages = max_page_number(first_html)

    results = parse_category_page(first_html, category_name)
    for page in range(2, total_pages + 1):
        time.sleep(0.5)  # вежливая пауза между запросами
        html = fetch(f"{first_url}?PAGEN_1={page}")
        results.extend(parse_category_page(html, category_name))
    return results


def main() -> None:
    all_items: list[dict] = []
    for slug, category_name in CATEGORIES.items():
        print(f"[scrape] {category_name} ({slug})...", file=sys.stderr)
        try:
            items = scrape_category(slug, category_name)
        except requests.RequestException as exc:
            print(f"[scrape] ошибка на категории {slug}: {exc}", file=sys.stderr)
            continue
        print(f"[scrape]   найдено {len(items)} позиций", file=sys.stderr)
        all_items.extend(items)

    print("[scrape] adilet.net (плёнка ПВХ)...", file=sys.stderr)
    try:
        adilet_items = scrape_adilet.scrape_all()
        print(f"[scrape]   найдено {len(adilet_items)} позиций", file=sys.stderr)
        all_items.extend(adilet_items)
    except Exception as exc:  # noqa: BLE001 - не хотим ронять весь скрапинг из-за одного источника
        print(f"[scrape] ошибка при скрапинге adilet.net: {exc}", file=sys.stderr)

    print("[scrape] kira-group.kz (плёнка ПВХ)...", file=sys.stderr)
    try:
        kira_items = scrape_kira.scrape_all()
        print(f"[scrape]   найдено {len(kira_items)} позиций", file=sys.stderr)
        all_items.extend(kira_items)
    except Exception as exc:  # noqa: BLE001 - не хотим ронять весь скрапинг из-за одного источника
        print(f"[scrape] ошибка при скрапинге kira-group.kz: {exc}", file=sys.stderr)

    print("[scrape] interstone.kz (акриловый камень GRANDEX)...", file=sys.stderr)
    try:
        interstone_items = scrape_interstone.scrape_all()
        print(f"[scrape]   найдено {len(interstone_items)} позиций", file=sys.stderr)
        all_items.extend(interstone_items)
    except Exception as exc:  # noqa: BLE001 - не хотим ронять весь скрапинг из-за одного источника
        print(f"[scrape] ошибка при скрапинге interstone.kz: {exc}", file=sys.stderr)

    print("[scrape] profikz.kz (ЛДСП и столешницы EGGER, Австрия)...", file=sys.stderr)
    try:
        profikz_items = scrape_profikz.scrape_all()
        print(f"[scrape]   найдено {len(profikz_items)} позиций", file=sys.stderr)
        all_items.extend(profikz_items)
    except Exception as exc:  # noqa: BLE001 - не хотим ронять весь скрапинг из-за одного источника
        print(f"[scrape] ошибка при скрапинге profikz.kz: {exc}", file=sys.stderr)

    # убираем дубликаты по id, если товар встретился в нескольких категориях
    seen = {}
    for item in all_items:
        seen[item["id"]] = item
    unique_items = list(seen.values())

    # Скачиваем и сжимаем фото каждого товара локально (data/images/), вместо
    # того чтобы хранить в materials.json прямые внешние ссылки на em-c.kz/
    # adilet.net/interstone.kz/kira-group.kz. Инкрементально: уже скачанные
    # фото не трогаем (см. docstring image_utils.py), поэтому при ежедневном
    # запуске обрабатываются по сути только новые товары.
    print("[scrape] скачивание и сжатие фото...", file=sys.stderr)
    for item in unique_items:
        image_utils.process_item_images(item, site_of(item["id"]))

    # Чистим фото товаров, которых больше нет в свежем каталоге (сняты с
    # продажи у источника и т.п.) — иначе data/images/ будет бесконечно расти.
    ids_by_site: dict[str, set] = {
        "emc": set(), "adilet": set(), "interstone": set(), "kira": set(), "profikz": set()
    }
    for item in unique_items:
        ids_by_site[site_of(item["id"])].add(item["id"])
    image_utils.cleanup_orphans(ids_by_site)

    unique_items.sort(key=lambda x: (x["category"], x["name"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(unique_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[scrape] готово: {len(unique_items)} товаров -> {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
