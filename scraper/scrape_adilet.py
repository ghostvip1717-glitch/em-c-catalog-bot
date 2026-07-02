#!/usr/bin/env python3
"""
Скрапер плёнки ПВХ с adilet.net (https://adilet.net/shop/plenka-pvh/).

Особенность этого сайта: списки товаров на страницах категорий (SOLID COLOR,
WOOD, TEXTURE) подгружаются через JavaScript/AJAX и недоступны простым
GET-запросом. Поэтому список товарных slug'ов собран один раз вручную через
браузер (см. SLUGS_BY_CATEGORY ниже) и захардкожен. Страницы отдельных
товаров (https://adilet.net/all/<slug>/), наоборот, обычный статический
HTML — их можно спокойно обходить requests'ом, поэтому имя и фото каждого
товара всегда актуальны на момент запуска скрипта.

Если на сайте появятся новые декоры, их slug нужно будет добавить в список
вручную (или переснять список через браузер) — полностью автоматическое
обновление списка потребовало бы headless-браузер в CI.
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://adilet.net"

SLUGS_BY_CATEGORY: dict[str, list[str]] = {
    "ПВХ плёнка: Wood": [
        "arbor-ar-01-funduk", "arbor-ar-02-piniya", "arbor-ar-03-pekan",
        "arbor-ar-04-makadami", "arbor-ar-05-betel", "arbor-ar-06-keshyu",
        "arbor-ar-07-chilim", "arbor-ar-08-kanarium", "art-wood-aw-06-klej",
        "art-wood-aw-01-snou", "art-wood-aw-13-sirokko", "art-wood-aw-14-karif",
        "art-wood-aw-02-kejmstoun", "art-wood-aw-03-send", "art-wood-aw-05-pit",
        "be-08-fodzha", "be-01-ancio", "be-04-kapri", "be-05-paviya",
        "be-07-ustika", "deep-wood-dw-011-platan", "deep-wood-dw-001-amarant",
        "deep-wood-dw-002-lipa", "deep-wood-dw-004-topol", "deep-wood-dw-010-tis",
        "dream-wood-mokko-0010-w18p", "dream-wood-belyj-1084-w18p",
        "dream-wood-grafit-0020-w18p", "dream-wood-metall-0022-w18p",
        "kombat-mk-26", "kombat-mk-19", "kombat-mk-20", "kombat-mk-21",
        "kombat-mk-22", "kombat-mk-23", "kombat-mk-24", "kombat-mk-25",
        "rift-rf-09-kattara", "rift-rf-01-assal", "rift-rf-02-afar",
        "rift-rf-03-garda", "rift-rf-04-ghor", "rift-rf-05-danakil",
        "rift-rf-07-ikariya", "rift-rf-08-lut", "venge-1998-b",
        "beloe-derevo-1155-bd", "akaciya-svetlaya-e1201-h8p",
        "akaciya-temnaya-e1202-h8p",
        "altajskaya-listvennica-temnaya-a2901-n9r",
        "buk-naturalnyj-mbp-2050-2", "vanilnoe-derevo-rr101",
    ],
    "ПВХ плёнка: Solid Color": [
        "al-01-ageratum", "al-02-muskari", "al-03-viola", "al-04-shabo",
        "al-06-kosmeya", "al-07-obrieta", "al-08-korall", "alda-al-10-garvish",
    ],
    "ПВХ плёнка: Texture": [
        "a-001-topaz", "a-002-albit", "a-004-serdolik", "a-005-morion",
        "a-006-oniks", "a-007-aleksandrit", "a-008-sapfir", "carbon-cbr-1-egret",
        "carbon-cbr-4-spejs", "carbon-cbr-2-obsidian", "carbon-cbr-3-shejd",
        "donata-da-14-torrone", "donata-da-13-spumoni", "donata-da-05-kannolo",
        "donata-da-06-kapreze", "donata-da-07-kolomba", "donata-da-08-nochiata",
        "donata-da-09-bushe", "donata-da-10-pandora", "ion-in-07-shedar",
        "ion-in-11-shaula", "ion-in-01-regul", "ion-in-02-spika",
        "ion-in-03-kapella", "ion-in-04-kanopus", "ion-in-05-fegda",
        "ion-in-06-kastor", "kombat-mk-08", "kombat-mk-01", "kombat-mk-02",
        "kombat-mk-03", "kombat-mk-04", "kombat-mk-05", "kombat-mk-06",
        "kombat-mk-07", "ma-05-uistler", "ma-01-gejranger", "marble-ma-21-etna",
        "marble-ma-22-agilera", "ma-02-kajlas", "ma-03-rejnir", "ma-11-ficroj",
        "ma-09-pilatus", "marble-ma-23-marra", "marble-ma-24-kroskat",
        "ma-10-krejdl", "shell-sh-08-bubles", "shell-sh-01-skafarka",
        "shell-sh-02-aulika", "shell-sh-03-galeya", "shell-sh-04-mureks",
        "shell-sh-05-lambis", "shell-sh-06-cipreya", "shell-sh-07-nassa",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

BG_IMAGE_RE = re.compile(r'background-image:\s*url\(["\']?([^"\')]+)["\']?\)')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_product_page(html: str, slug: str, category_name: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.style_page_name") or soup.select_one("h1")
    if not title_el:
        return None
    name = title_el.get_text(strip=True)

    image = None
    candidates = soup.select('[class*="rct_gallery_content_items_item"]')

    def sort_key(el):
        classes = el.get("class") or []
        class_str = " ".join(classes)
        is_first_slide = "item-0" in class_str
        is_cloned = "slick-cloned" in classes
        return (not is_first_slide, is_cloned)

    candidates.sort(key=sort_key)
    for el in candidates:
        # Часть карточек используют PhotoSwipe-галерею: полноразмерное фото
        # лежит прямо в href, а style — просто плейсхолдер-лоадер до JS-подгрузки.
        href = el.get("href") or ""
        if href and "loader" not in href:
            image = href
            break
        style = el.get("style") or ""
        m = BG_IMAGE_RE.search(style)
        if m and "loader" not in m.group(1):
            image = m.group(1)
            break
    if image and image.startswith("/"):
        image = BASE_URL + image

    return {
        "id": "adilet_" + slug,
        "name": name,
        "category": category_name,
        "url": f"{BASE_URL}/all/{slug}/",
        "image": image,
    }


def scrape_all() -> list[dict]:
    results: list[dict] = []
    for category_name, slugs in SLUGS_BY_CATEGORY.items():
        print(f"[scrape_adilet] {category_name}: {len(slugs)} товаров...", file=sys.stderr)
        for slug in slugs:
            if slug.endswith("-test"):
                continue
            url = f"{BASE_URL}/all/{slug}/"
            try:
                html = fetch(url)
                item = parse_product_page(html, slug, category_name)
                if item:
                    results.append(item)
            except requests.RequestException as exc:
                print(f"[scrape_adilet] ошибка на {slug}: {exc}", file=sys.stderr)
            time.sleep(0.3)  # вежливая пауза между запросами
    return results


if __name__ == "__main__":
    # Самостоятельный запуск: печатает JSON в stdout (для отладки).
    items = scrape_all()
    print(json.dumps(items, ensure_ascii=False, indent=2))
