#!/usr/bin/env python3
"""
Скрапер плёнки ПВХ и мебельных тканей с adilet.net
(https://adilet.net/shop/plenka-pvh/, https://adilet.net/shop/mebelnye-tkani/).

Особенность этого сайта: списки товаров на страницах категорий (и плёнки —
SOLID COLOR/WOOD/TEXTURE, и тканей — Велюр/Шенилл/Иск.кожа/Иск.замша/Рогожка)
подгружаются через JavaScript/AJAX и недоступны простым GET-запросом. Поэтому
список товарных slug'ов собран заранее и захардкожен: SLUGS_BY_CATEGORY
(плёнка) — вручную через браузер; TKANI_SLUGS_BY_CATEGORY (ткани, 726 позиций
по 5 категориям) — через отдельный Playwright-скрипт
(scrape_adilet_tkani_slugs.py в корне репозитория), т.к. у тканей на порядок
больше позиций (одних коллекций Велюра — 44+) и вручную не собрать. Страницы
отдельных товаров (https://adilet.net/all/<slug>/), наоборот, обычный
статический HTML — их можно спокойно обходить requests'ом, поэтому имя и
фото каждого товара всегда актуальны на момент запуска скрипта.

Если на сайте появятся новые декоры, их slug нужно будет добавить в список
вручную (для плёнки) или перезапустить scrape_adilet_tkani_slugs.py (для
тканей) — полностью автоматическое обновление списка потребовало бы
headless-браузер прямо в CI.
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

# Мебельные ткани (Велюр/Шенилл/Иск.кожа/Иск.замша/Рогожка) — 726 позиций.
# Собраны отдельным Playwright-скриптом (scrape_adilet_tkani_slugs.py),
# т.к. вручную (как плёнку) их не пересчитать — см. докстринг файла выше.
TKANI_SLUGS_BY_CATEGORY: dict[str, list[str]] = {
    "Ткани: Велюр": [
        "3d-cotton-1", "3d-cotton-2", "3d-cotton-3", "3d-cotton-4",
        "3d-cotton-5", "3d-cotton-6", "3d-cotton-7", "3d-cotton-8",
        "alpha-1", "alpha-2", "alpha-3", "alpha-4",
        "annabel-1", "annabel-2", "annabel-3", "annabel-4",
        "annabel-5", "annabel-6", "annabel-7", "annabel-8",
        "aura-1", "aura-2", "aura-3", "aura-4",
        "aura-5", "aura-6", "aura-7", "aura-8",
        "auralite-1", "auralite-2", "auralite-3", "auralite-4",
        "auralite-5", "auralite-6", "auralite-7", "auralite-8",
        "aurus-1", "aurus-2", "aurus-3", "aurus-4",
        "aurus-5", "aurus-6", "aurus-7", "aurus-8",
        "avatr-1", "avatr-2", "avatr-3", "avatr-4",
        "avatr-5", "avatr-6", "avatr-7", "avatr-8",
        "avatr-lite-1", "avatr-lite-2", "avatr-lite-3", "avatr-lite-4",
        "avatr-lite-5", "avatr-lite-6", "avatr-lite-7", "avatr-lite-8",
        "beauty-1", "beauty-10", "beauty-11", "beauty-12",
        "beauty-13", "beauty-14", "beauty-8", "beauty-9",
        "brabus-1", "brabus-2", "brabus-3", "brabus-4",
        "brabus-5", "brabus-6", "brabus-7", "brabus-8",
        "butterflies-2d-1-color", "butterflies-2d-2-brown", "butterflies-2d-3-blue", "butterflies-3d-2-brown",
        "butterflies-3d-3-blue", "classic-check-1", "classic-check-3", "classic-check-4",
        "classic-check-5", "classic-check-6", "classic-com-1", "classic-com-2",
        "classic-com-5", "crush-1", "crush-2", "crush-3",
        "crush-4", "crush-5", "crush-6", "crush-7",
        "crush-8", "desert-1", "desert-2", "desert-3",
        "desert-4", "desert-5", "desert-6", "desert-7",
        "desert-8", "fortiz-000", "fortiz-100", "fortiz-1015",
        "fortiz-1016", "fortiz-1021", "fortiz-1022", "fortiz-1023",
        "fortiz-673", "galaxy-1", "galaxy-2", "galaxy-3",
        "galaxy-4", "galaxy-5", "galaxy-6", "galaxy-7",
        "galaxy-8", "galaxy-lite-1", "galaxy-lite-2", "galaxy-lite-3",
        "galaxy-lite-4", "galaxy-lite-5", "galaxy-lite-6", "galaxy-lite-7",
        "galaxy-lite-8", "galaxy-ultra-101", "galaxy-ultra-102", "galaxy-ultra-103",
        "galaxy-ultra-104", "galaxy-ultra-105", "galaxy-ultra-106", "galaxy-ultra-107",
        "galaxy-ultra-121", "germes-01", "germes-02", "germes-03",
        "germes-04", "germes-05", "germes-06", "germes-07",
        "germes-08", "grizzly-1", "grizzly-2", "grizzly-3",
        "grizzly-4", "grizzly-5", "grizzly-6", "grizzly-7",
        "grizzly-8", "infiniti-1", "infiniti-2", "infiniti-3",
        "infiniti-4", "infiniti-5", "infiniti-6", "infiniti-7",
        "infiniti-8", "lamborghini-1", "lamborghini-2", "lamborghini-3",
        "lamborghini-4", "lamborghini-5", "lamborghini-6", "lamborghini-7",
        "lamborghini-8", "mabini-1", "mabini-2", "mabini-3",
        "mabini-4", "mabini-5", "mabini-6", "mabini-7",
        "mabini-8", "macan-1", "macan-2", "macan-3",
        "macan-4", "macan-5", "macan-6", "macan-7",
        "macan-8", "marketplace-v-1", "marketplace-v-2", "marketplace-v-3",
        "marketplace-v-4", "marketplace-v-5", "marketplace-v-6", "marketplace-v-7",
        "marketplace-v-8", "maserati-1", "maserati-2", "maserati-3",
        "maserati-4", "maserati-5", "maserati-6", "maserati-7",
        "maserati-8", "mikea-1", "mikea-2", "mikea-3",
        "mikea-4", "mikea-5", "mikea-6", "mikea-7",
        "mikea-8", "moon-1", "moon-2", "moon-3",
        "moon-4", "moon-5", "moon-6", "moon-7",
        "moon-8", "nord-1", "nord-2", "nord-3",
        "nord-4", "nord-5", "nord-6", "nord-7",
        "nord-8", "olivia-1", "olivia-2", "olivia-3",
        "olivia-4", "olivia-5", "olivia-6", "olivia-7",
        "olivia-com-1", "olivia-com-2", "olivia-com-3", "olivia-com-4",
        "olivia-com-5", "olivia-com-6", "olivia-com-7", "omega-01",
        "omega-02", "omega-03", "omega-04", "omega-05",
        "omega-06", "omega-07", "onyx-01", "onyx-02",
        "onyx-03", "onyx-04", "onyx-05", "onyx-06",
        "onyx-07", "onyx-08", "polo-1", "polo-2",
        "polo-3", "polo-4", "polo-5", "polo-6",
        "polo-7", "polo-8", "romeo-1", "romeo-3",
        "romeo-4", "romeo-5", "romeo-6", "romeo-7",
        "romeo-8", "romeo2", "shelby-01", "shelby-02",
        "shelby-03", "shelby-04", "shelby-05", "shelby-06",
        "shelby-07", "shelby-08", "sofitel-3d-1", "sofitel-3d-10",
        "sofitel-3d-6", "sofitel-3d-7", "sofitel-3d-8", "sofitel-3d-9",
        "sofitel-com-10", "sofitel-com-7", "stream-28", "stream-29",
        "stream-30", "stream-31", "stream-32", "stream-33",
        "stream-38", "stream-40", "tayson-1", "tayson-13",
        "tayson-2", "tayson-3", "tayson-4", "tayson-5",
        "tayson-6", "tayson-7", "teddy-pro-1", "teddy-pro-2",
        "teddy-pro-3", "teddy-pro-4", "teddy-pro-5", "teddy-pro-6",
        "teddy-pro-7", "teddy-pro-9", "tiza-1", "tiza-2",
        "tiza-3", "tiza-4", "ultra-01", "ultra-02",
        "ultra-03", "ultra-04", "ultra-05", "ultra-06",
        "ultra-07", "ultra-08", "ultraloft-1", "ultraloft-2",
        "ultraloft-3", "ultraloft-4", "ultraloft-5", "ultraloft-6",
        "ultraloft-7", "ultraloft-8", "urban-1", "urban-2",
        "urban-3", "urban-4", "urban-5", "urban-6",
        "urban-7", "urban-8", "veluta-lux-01", "veluta-lux-03",
        "veluta-lux-05", "veluta-lux-06", "veluta-lux-07", "veluta-lux-08",
        "veluta-lux-09", "veluta-lux-10", "velvet-1", "velvet-2",
        "velvet-3", "velvet-4", "velvet-5", "velvet-6",
        "velvet-7", "velvet-8",
    ],
    "Ткани: Шенилл": [
        "chiron-1", "chiron-2", "chiron-3", "chiron-4",
        "chiron-5", "chiron-6", "chiron-7", "chiron-8",
        "minotti-1", "minotti-2", "minotti-3", "minotti-4",
        "minotti-5", "minotti-6", "minotti-7", "minotti-8",
        "phantom-1", "phantom-2", "phantom-3", "phantom-4",
        "phantom-5", "phantom-6", "phantom-7", "phantom-8",
        "picasso-1", "picasso-2", "picasso-3", "picasso-4",
        "picasso-5", "picasso-6", "picasso-7", "picasso-8",
        "sky-1", "sky-2", "sky-3", "sky-4",
        "sky-5", "sky-6", "sky-7", "sky-8",
        "slamet-1", "slamet-14", "slamet-2", "slamet-3",
        "slamet-4", "slamet-5", "slamet-6", "slamet-7",
        "storm-1", "storm-2", "storm-3", "storm-4",
        "storm-5", "storm-6", "storm-7", "storm-8",
    ],
    "Ткани: Искусственная кожа": [
        "avenir-plus-1", "avenir-plus-11", "avenir-plus-15", "avenir-plus-19",
        "avenir-plus-25", "avenir-plus-28", "avenir-plus-4", "avenir-plus-5",
        "bellagio-1", "bellagio-2", "bellagio-3", "bellagio-4",
        "bellagio-5", "bellagio-6", "bellagio-7", "bellagio-8",
        "belucci-1", "belucci-2", "belucci-3", "belucci-4",
        "bosco-1", "bosco-2", "bosco-3", "bosco-4",
        "bosco-5", "bosco-6", "bosco-7", "bosco-8",
        "como-1", "como-2", "como-3", "como-4",
        "como-5", "como-6", "como-7", "como-8",
        "dallas-amber", "dallas-biscuit", "dallas-black", "dallas-brown",
        "dallas-whiskey", "dallas-white", "elite-lux-1", "elite-lux-2",
        "elite-lux-3", "elite-lux-4", "elite-lux-5", "elite-lux-6",
        "elite-lux-7", "elite-lux-8", "megapolis-1", "megapolis-2",
        "megapolis-3", "megapolis-4", "megapolis-5", "megapolis-6",
        "milan-1", "milan-2", "milan-3", "milan-4",
        "milan-5", "milan-6", "milan-7", "milan-8",
        "only-white-01", "rich-1", "rich-11", "rich-12",
        "rich-13", "rich-14", "rich-15", "rich-16",
        "rich-17", "soft-1", "soft-2", "soft-3",
        "soft-4", "soft-5", "soft-6", "soft-7",
        "soft-8", "soft-touch-1", "soft-touch-2", "soft-touch-3",
        "soft-touch-4", "soft-touch-5", "soft-touch-6", "soft-touch-7",
        "soft-touch-8", "victoria-black", "victoria-bordo", "victoria-brown",
        "victoria-brown-dark", "victoria-cream", "victoria-orange", "victoria-white",
        "zeekr-1", "zeekr-2", "zeekr-3", "zeekr-4",
        "zeekr-5", "zeekr-6", "zeekr-7", "zeekr-8",
    ],
    "Ткани: Искусственная замша": [
        "bentli-01", "bentli-02", "bentli-03", "bentli-04",
        "bentli-05", "bentli-06", "bentli-07", "bentli-08",
        "bugatti-01", "bugatti-02", "bugatti-03", "bugatti-04",
        "bugatti-05", "dakar-1", "dakar-2", "dakar-3",
        "dakar-4", "dakar-5", "dakar-6", "dakar-7",
        "dakar-8", "enzo-1", "enzo-2", "enzo-3",
        "enzo-4", "enzo-5", "enzo-6", "enzo-7",
        "enzo-8", "flagman-1", "flagman-2", "flagman-3",
        "flagman-4", "flagman-5", "gamma-1", "gamma-2",
        "gamma-3", "gamma-4", "gamma-5", "gamma-6",
        "gamma-7", "gamma-8", "gaudi-01", "gaudi-02",
        "gaudi-03", "gaudi-04", "gaudi-05", "loft-01",
        "loft-02", "loft-03", "loft-04", "loft-05",
        "loft-06", "loft-07",
    ],
    "Ткани: Рогожка": [
        "beta-1", "beta-2", "beta-3", "beta-4",
        "beta-5", "beta-6", "beta-7", "beta-8",
        "blik-1", "blik-2", "blik-3", "blik-4",
        "blik-5", "chester-1", "chester-2", "chester-3",
        "chester-4", "chester-5", "chester-6", "chester-7",
        "cuba-1", "cuba-2", "cuba-3", "cuba-4",
        "cuba-5", "cuba-6", "etro-01", "etro-02",
        "etro-03", "etro-04", "etro-05", "etro-06",
        "etro-07", "etro-08", "kln-01", "kln-02",
        "kln-03", "kln-04", "kln-05", "kln-06",
        "koln-10", "koln-9", "lester-14", "lester-16",
        "lester-17", "lester-3", "lester-4", "lester-6",
        "lester-8", "lester-9", "loner-1", "loner-2",
        "loner-3", "loner-4", "loner-5", "loner-7",
        "loner-8", "marketplace-r-1", "marketplace-r-2", "marketplace-r-3",
        "marketplace-r-4", "marketplace-r-5", "marketplace-r-6", "marketplace-r-7",
        "marketplace-r-8", "matrix-1", "matrix-2", "matrix-3",
        "matrix-4", "matrix-5", "matrix-6", "matrix-7",
        "miami-1", "miami-2", "miami-3", "miami-4",
        "miami-5", "miami-6", "monaco-01", "monaco-02",
        "monaco-03", "monaco-04", "monaco-05", "monaco-06",
        "monaco-07", "monaco-08", "next-01", "next-02",
        "next-03", "next-04", "next-05", "next-06",
        "next-07", "next-08", "nova-01", "nova-02",
        "nova-03", "nova-04", "nova-05", "nova-06",
        "nova-07", "nova-08", "pixel-01", "pixel-02",
        "pixel-03", "pixel-04", "pixel-05", "pixel-06",
        "pixel-07", "pixel-08", "quantum-1", "quantum-12",
        "quantum-2", "quantum-48", "quantum-5", "quantum-50",
        "quantum-617", "quantum-9", "smart-01", "smart-02",
        "smart-03", "smart-04", "smart-05", "smart-06",
        "smart-07", "smart-08", "space-01", "space-02",
        "space-03", "space-04", "space-05", "space-06",
        "space-07", "space-08", "step-01", "step-02",
        "step-03", "step-04", "step-05", "step-06",
        "step-07", "step-08", "strong-1", "strong-2",
        "strong-3", "strong-4", "strong-5", "strong-6",
        "strong-plus-01", "strong-plus-02", "tesla-01", "tesla-02",
        "tesla-03", "tesla-04", "tesla-05", "tesla-06",
        "tesla-07", "tesla-08",
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
    # ПВХ плёнка + мебельные ткани — те же parse_product_page/URL-паттерн
    # (/all/<slug>/), поэтому просто объединяем оба словаря slug'ов и гоняем
    # одним циклом.
    all_categories: dict[str, list[str]] = {**SLUGS_BY_CATEGORY, **TKANI_SLUGS_BY_CATEGORY}
    for category_name, slugs in all_categories.items():
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
