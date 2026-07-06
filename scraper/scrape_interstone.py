#!/usr/bin/env python3
"""
Скрапер акрилового и кварцевого камня с interstone.kz:
- Акриловый камень GRANDEX (https://interstone.kz/stones/akrilovyy-kamen/grandex/colors)
- Кварцевый камень: Caesarstone, Avant Quartz, GRANDEX Quartz
  (https://interstone.kz/stones/kvarcevyy-kamen/<brand>/colors)

Особенность этого сайта: страница палитры цветов подгружает карточки по кнопке
"Показать ещё" через JavaScript (без отдельного XHR с JSON — данные уже лежат
в DOM, кнопка просто показывает следующую порцию), поэтому полный список
slug'ов не вытащить простым GET-запросом на страницу палитры. Для акрила GRANDEX
он в своё время был собран вручную через браузер (см. SLUGS ниже). Для кварца
(3 бренда, 100+ декоров суммарно) удалось выгрузить полный и куда более
надёжный список прямо из https://interstone.kz/sitemap.xml (там просто лежат
ссылки на все страницы цветов) — см. QUARTZ_SLUGS_BY_BRAND ниже.
Страницы отдельных цветов (https://interstone.kz/stones/.../colors/<slug>),
наоборот, обычный статический HTML — их можно спокойно обходить requests'ом,
поэтому имя и фото каждого цвета всегда актуальны на момент запуска скрипта.

Если появятся новые декоры, их slug нужно будет добавить в список вручную
(для кварца — проще всего перепроверить https://interstone.kz/sitemap.xml).
"""

import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://interstone.kz"
CATEGORY_NAME = "Акриловый камень GRANDEX"

# Кварцевые бренды: slug раздела в URL -> человекочитаемое название категории
# в приложении. Префикс "Кварцевый камень" в названии категории используется
# фронтендом (index.html, siteGroupOf) для группировки под общий источник
# INTERSTONE.KZ вместе с акриловым камнем GRANDEX — см. комментарий там.
QUARTZ_CATEGORIES: dict[str, str] = {
    "caesarstone": "Кварцевый камень Caesarstone",
    "avant-quartz": "Кварцевый камень Avant Quartz",
    "grandex-quartz": "Кварцевый камень GRANDEX Quartz",
}

QUARTZ_SLUGS_BY_BRAND: dict[str, list[str]] = {
    "caesarstone": [
        "sleek-concrete", "vanilla-noir", "pure-white", "jet-black",
        "cloudburst-concrete", "topus-concrete", "rugged-concrete",
        "airy-concrete", "excava", "london-grey", "piatra-grey",
        "alpine-mist", "symphony-grey", "frosty-carrina", "taj-royale",
        "dreamy-marfil", "coastal-grey", "moorland-fog", "bianco-drift",
        "woodlands", "black-tempal", "5143-white-attica",
    ],
    "avant-quartz": [
        "burbonne", "limuzen", "provans", "korsika", "savoyya",
        "kalakatta-eno", "statuario-lill", "akvitaniya-blanka",
        "kalakatta-ayachcho", "kalakatta-dofine", "gris-fonse",
        "kalakatta-le-nor", "kalakatta-arras", "q740-calacatta-venato",
        "q765-nero-marquina", "kallakata-bern", "calacatta-marsel",
        "calacatta-shenonso", "calacatta-bomenil", "calacatta-mon-sen-mishel",
        "calacatta-versal", "calacatta-pierfon", "8100mulen",
        "calacatta-benak", "q101-gold-sand", "q102-white-sand",
        "q112-white-mirror", "q714-black-marble", "7888-calacatta-dinan",
        "8811-reze", "9212-saint-tropez", "q703-calacatta-borghini",
        "q131-black-sand", "q744-calacatta-bianco", "q757-calacatta-aurum",
        "q810-grey-glow", "q811-beton-white", "q880-beton-grey",
        "q718-carrara-moon", "9172-blave", "q930-royal-beige",
        "q931-hazel", "7810-calacatta-modane", "7970-calacatta-troyes",
        "7985-nicca-noir", "q797-calacatta-true-light", "q801-beton-marquina",
        "8580-tarn",
    ],
    "grandex-quartz": [
        "gq-403-modern-aspect", "gq-403m-modern-aspect",
        "gq-503-minimalist-perfection", "gq-510-gothic-black",
        "gq-511-japanese-harmony", "gq-511m-japanese-harmony",
        "gq-515-scandinavian-elegance", "gq-522-bohemian-luxury",
        "gq-531-vintage-pattern", "gq-538-art-deco", "gq-541-zen-serenity",
        "gq-543-fusion-inspiration", "gq-543m-fusion-inspiration",
        "gq-677-industrial-space", "gq-104-traditional-design",
        "gq-112-high-tech-style", "gq-122-eclectic-diversity",
        "gq-444m-timeless-classic", "gq-444-timeless-classic",
        "gq-500-colonial-style", "gq-510m-gothic-black",
        "gq-520-organic-modern", "gq-555-urban-loft",
        "gq-558-charming-provence", "gq-520m-organic-modern",
        "gq-575-nordic-light", "gq-560m-rustic-charm", "gq-590-baroque-glow",
        "gq-711-retro-spirit", "gq-716-futuristic-edge",
        "gq-723-italian-grace", "gq-727-bauhaus-vision",
        "gq-760-mexican-flair", "gq-777-eco-living", "gq-797-tropical-vibe",
    ],
}

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


def parse_product_page(html: str, slug: str, category_name: str, url_path: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.main-title") or soup.select_one("h1")
    if not title_el:
        return None
    name = title_el.get_text(strip=True)

    # Раньше фото искалось через img[src*="products-gallery"] с фолбэком на
    # "первый img в галерее" — но у части товаров реальные фото лежат по
    # другому пути (/media/images/1280/stones/GRANDEX/...), без "products-gallery"
    # в URL. Тогда селектор не находил совпадений, и фолбэк подхватывал первый
    # попавшийся <img> в блоке галереи — им оказывалась иконка стрелки
    # пагинации (rotator-arr-left.svg), которая в разметке идёт раньше фото.
    #
    # Теперь вместо привязки к конкретной подстроке пути берём ВСЕ <img> внутри
    # .product-gallery, что ведут на реальные загруженные фото (путь содержит
    # "/media/images/"), и явно отбрасываем иконки интерфейса (путь содержит
    # "/front/img/icon/" — стрелки, лупа, крестик и т.п.). Так же убираем
    # дубли между версией 1280px и 320px одного и того же файла.
    gallery = soup.select_one(".product-gallery")
    scope = gallery if gallery else soup

    images: list[str] = []
    seen_filenames: set[str] = set()
    for img in scope.select("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue
        if "/front/img/icon/" in src:
            continue  # иконки интерфейса (стрелки, лупа) — не фото товара
        if "/media/images/" not in src:
            continue
        if src.startswith("/"):
            src = BASE_URL + src
        # /media/images/1280/... и /media/images/320/... — одно и то же фото
        # в разных размерах; оставляем только первую (крупную, 1280) версию.
        filename = src.rsplit("/", 1)[-1]
        if filename in seen_filenames:
            continue
        seen_filenames.add(filename)
        images.append(src)

    if not images:
        print(f"[scrape_interstone] предупреждение: не найдено ни одного фото для {slug}", file=sys.stderr)

    return {
        "id": "interstone_" + slug,
        "name": name,
        "category": category_name,
        "url": f"{BASE_URL}{url_path}/{slug}",
        "image": images[0] if images else None,
        "images": images,
    }


def scrape_all() -> list[dict]:
    results: list[dict] = []

    print(f"[scrape_interstone] {CATEGORY_NAME}: {len(SLUGS)} товаров...", file=sys.stderr)
    acrylic_path = "/stones/akrilovyy-kamen/grandex/colors"
    for slug in SLUGS:
        url = f"{BASE_URL}{acrylic_path}/{slug}"
        try:
            html = fetch(url)
            item = parse_product_page(html, slug, CATEGORY_NAME, acrylic_path)
            if item:
                results.append(item)
        except requests.RequestException as exc:
            print(f"[scrape_interstone] ошибка на {slug}: {exc}", file=sys.stderr)
        time.sleep(0.3)  # вежливая пауза между запросами

    for brand_slug, slugs in QUARTZ_SLUGS_BY_BRAND.items():
        category_name = QUARTZ_CATEGORIES[brand_slug]
        brand_path = f"/stones/kvarcevyy-kamen/{brand_slug}/colors"
        print(f"[scrape_interstone] {category_name}: {len(slugs)} товаров...", file=sys.stderr)
        for slug in slugs:
            url = f"{BASE_URL}{brand_path}/{slug}"
            try:
                html = fetch(url)
                item = parse_product_page(html, slug, category_name, brand_path)
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
