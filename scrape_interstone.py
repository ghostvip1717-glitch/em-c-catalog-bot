#!/usr/bin/env python3
"""
Скрапер акрилового камня GRANDEX с interstone.kz
(https://interstone.kz/stones/akrilovyy-kamen/grandex/colors).

Особенность этого сайта: страница палитры цветов подгружает карточки по кнопке
"Показать ещё" через JavaScript (без отдельного XHR с JSON — данные уже лежат
в DOM, кнопка просто показывает следующую порцию), поэтому полный список
slug'ов собран один раз вручную через браузер (см. SLUGS ниже) и захардкожен.
Страницы отдельных цветов (https://interstone.kz/stones/akrilovyy-kamen/grandex/colors/<slug>),
наоборот, обычный статический HTML — их можно спокойно обходить requests'ом,
поэтому имя и фото каждого цвета всегда актуальны на момент запуска скрипта.

Если у GRANDEX появятся новые цвета, их slug нужно будет добавить в список
вручную (или переснять список через браузер).
"""

import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://interstone.kz"
CATEGORY_NAME = "Акриловый камень GRANDEX"

SLUGS: list[str] = [
    "c-808-rossano", "c-809-angiari", "m-605-notte-bianca", "m-610-amiata-bianca",
    "m-732-marble-mirage", "m-798-black-pearl", "m-724-cloud-concrete",
    "p119-whale-white", "m-701-hazel-flow", "m-707-noble-pearl",
    "m-717-shrimp-crust", "m-719-octopus-ink", "snow-pile", "a-427-primo",
    "d-313-milky-way", "d-314-arctic-ice", "d-315-spacemen-food",
    "s-204-creamy-sand", "p-104-pure-white", "c-801-arezzo", "c-802-piacenza",
    "c-803-salerno", "m-703-water-weed", "m-704-shell-surface",
    "m-705-lake-coast", "m-706-stormy-sea", "m-708-deep-water",
    "m-710-float-rock", "m-711-sparkling-wave", "m-712-stylish-moon",
    "m-713-whitesand-beach", "m-715-beton-bridge", "m-718-neptun-trident",
    "m-720-a-carrara-lunar", "m-723-a-timber-wolf", "m-727-a-venice",
    "cloudy-mount", "asphalt-material", "space-galaxy", "cotton-wool",
    "precious-stone", "citron-blossom", "historical-spot",
    "a-416-visible-horizon", "a-417-global-cruise", "a-419-cromium-atom",
    "a-421-coal-mine", "a-423-industrial-draft", "a-424-loft-design",
    "a-425-urban-project", "a-426-onyx", "a-428-andes", "a-429-conrete-quartz",
    "d-301-poppy-seed", "d-302-morning-coffee", "d-304-ice-cream",
    "d-307-aspen-pie", "d-308-cubic-mint", "d-309-mushroom-soup",
    "d-310-herbal-ash", "d-312-pietra-absorb", "d-318-velvet-bean",
    "d-320-soil", "j-504-cut-diamond", "j-505-pearl-necklace",
    "j-509-american-obsidian", "j-510-terazzo-bianco", "e-603-snowy-moscow",
    "e-605-indian-mantra", "e-609-business-tokio", "e-618-saturn-ring",
    "p-107-pure-red", "p-197-deep-sea", "p-198-mango", "p-199-pure-orange",
    "p-427-green-lime",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_product_page(html: str, slug: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.main-title") or soup.select_one("h1")
    if not title_el:
        return None
    name = title_el.get_text(strip=True)

    # Реальное фото товара всегда лежит под /media/images/... — в отличие от
    # служебных иконок галереи (стрелки rotator-arr-*.svg, лупа zoom.svg),
    # которые лежат под /front/img/icon/. Сам путь после /media/images/ у
    # разных карточек отличается (где-то .../products-gallery/Grandex/...,
    # где-то .../stones/GRANDEX/...), поэтому фильтруем по общему признаку.
    image = None
    gallery = soup.select_one(".product-gallery")
    scope = gallery if gallery else soup
    candidates = [
        img for img in scope.select("img")
        if "/media/images/" in (img.get("src") or img.get("data-src") or "")
    ]

    def sort_key(img):
        parent = img.find_parent()
        classes = " ".join(parent.get("class") or []) if parent else ""
        is_current = "slick-current" in classes
        return not is_current

    candidates.sort(key=sort_key)
    if candidates:
        img = candidates[0]
        image = img.get("src") or img.get("data-src")
    if image and image.startswith("/"):
        image = BASE_URL + image

    return {
        "id": "interstone_" + slug,
        "name": name,
        "category": CATEGORY_NAME,
        "url": f"{BASE_URL}/stones/akrilovyy-kamen/grandex/colors/{slug}",
        "image": image,
    }


def scrape_all() -> list[dict]:
    results: list[dict] = []
    print(f"[scrape_interstone] {CATEGORY_NAME}: {len(SLUGS)} товаров...", file=sys.stderr)
    for slug in SLUGS:
        url = f"{BASE_URL}/stones/akrilovyy-kamen/grandex/colors/{slug}"
        try:
            html = fetch(url)
            item = parse_product_page(html, slug)
            if item:
                results.append(item)
        except requests.RequestException as exc:
            print(f"[scrape_interstone] ошибка на {slug}: {exc}", file=sys.stderr)
        time.sleep(0.3)  # вежливая пауза между запросами
    return results


if __name__ == "__main__":
    # Самостоятельный запуск: печатает JSON в stdout (для отладки).
    items = scrape_all()
    print(json.dumps(items, ensure_ascii=False, indent=2))
