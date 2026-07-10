#!/usr/bin/env python3
"""
Скрапер HPL-декоров с лендинга dtail.kz/HPL-2 (конструктор Creatium).

Каталог декоров подгружается в модальное окно через Creatium delivery-builder
(action=async): в ответе JS-объект cr._async.modals содержит HTML всех модалок,
включая сетку «Каталог декоров» (кнопка «ОТКРЫТЬ» в блоке «ДЕКОРЫ»).

Категория в каталоге: «Столешницы: HPL (Dtail)» — попадает в группу
stoleshnitsy на фронтенде (siteGroupOf по префиксу «Столешницы»).
"""

from __future__ import annotations

import json
import re
import sys
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://dtail.kz/HPL-2"
CATEGORY = "Столешницы: HPL (Dtail)"
MODAL_DATA_ID = "cvet3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": BASE_URL,
}

ASYNC_KEY_RE = re.compile(r"delivery-builder\?action=async&key=([a-f0-9]+)")
MODAL_UID_RE = re.compile(
    rf'data-id="{MODAL_DATA_ID}"[^>]*>\s*<div data-uid="([^"]+)"',
    re.DOTALL,
)
ASYNC_PAYLOAD_RE = re.compile(r"cr\._async\s*=\s*(\{.*\})\s*;?\s*$", re.DOTALL)
BG_IMAGE_RE = re.compile(r'url\(["\']?(.*?)["\']?\)')
CYRILLIC_RE = re.compile(r"[А-ЯЁ]")
JUNK_WORDS = ("ПОСТАВЩИК", "ОТДЕЛКА", "ФАСАД", "ПАНЕЛ")

TRANSLIT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def slugify(name: str) -> str:
    """Транслитерация названия декора в безопасный slug для id."""
    lower = name.lower().strip()
    parts: list[str] = []
    for ch in lower:
        if ch in TRANSLIT:
            parts.append(TRANSLIT[ch])
        elif ch.isalnum():
            parts.append(ch)
        elif ch in {" ", "-", "_"}:
            parts.append("_")
    slug = re.sub(r"_+", "_", "".join(parts)).strip("_")
    return slug or "decor"


def normalize_image_url(url: str) -> str:
    """Убирает Creatium-суффиксы (#{"size":...}) и декодирует URL."""
    return unquote(url.split("#", 1)[0].replace("&quot;", ""))


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_async_key(page_html: str) -> str:
    match = ASYNC_KEY_RE.search(page_html)
    if not match:
        raise ValueError("не найден ключ delivery-builder action=async")
    return match.group(1)


def extract_modal_uid(page_html: str) -> str | None:
    match = MODAL_UID_RE.search(page_html)
    return match.group(1) if match else None


def load_async_modals(page_html: str) -> dict[str, str]:
    async_key = extract_async_key(page_html)
    raw = fetch(f"https://dtail.kz/app/4.2/delivery-builder?action=async&key={async_key}")
    match = ASYNC_PAYLOAD_RE.search(raw)
    if not match:
        raise ValueError("не удалось разобрать cr._async из delivery-builder")
    payload = json.loads(match.group(1))
    modals = payload.get("modals")
    if not isinstance(modals, dict):
        raise ValueError("в cr._async нет секции modals")
    return modals


def pick_decor_modal_html(modals: dict[str, str], page_html: str) -> str:
    uid = extract_modal_uid(page_html)
    if uid and uid in modals:
        return modals[uid]

    for html in modals.values():
        if "Каталог декоров" in html:
            return html

    raise ValueError("модалка с каталогом декоров не найдена")


def image_url_from_widget(img_div) -> str | None:
    bg = img_div.select_one(".bgimage")
    if bg:
        match = BG_IMAGE_RE.search(bg.get("style") or "")
        if match:
            return normalize_image_url(match.group(1))

    for el in img_div.select("[data-lazy-bgimage]"):
        url = (el.get("data-lazy-bgimage") or "").strip()
        if url:
            return normalize_image_url(url)

    noscript = img_div.select_one("noscript img")
    if noscript and noscript.get("src"):
        return normalize_image_url(noscript["src"])
    return None


def is_decor_name(name: str) -> bool:
    """Оставляем только названия декоров HPL из сетки каталога."""
    if not name or len(name) > 40:
        return False
    if ":" in name or "\n" in name:
        return False
    if any(word in name for word in JUNK_WORDS):
        return False
    if not CYRILLIC_RE.search(name):
        return False
    return name.upper() == name


def parse_decor_grid(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    pairs: list[tuple[str, str]] = []
    for cont in soup.select(".cont"):
        img_div = cont.select_one(".node.widget-image")
        text_div = cont.select_one(".node.widget-text")
        if not img_div or not text_div:
            continue
        name = text_div.get_text(strip=True)
        url = image_url_from_widget(img_div)
        if not url or "creatium.ru" not in url:
            continue
        if not is_decor_name(name):
            continue
        pairs.append((name, url))
    return pairs


def scrape_all() -> list[dict]:
    try:
        page_html = fetch(BASE_URL)
        modals = load_async_modals(page_html)
        decor_html = pick_decor_modal_html(modals, page_html)
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        print(f"[scrape_dtail] ошибка загрузки каталога: {exc}", file=sys.stderr)
        return []

    raw_pairs = parse_decor_grid(decor_html)
    if not raw_pairs:
        print("[scrape_dtail] декоры не найдены в модальном окне", file=sys.stderr)
        return []

    by_name: dict[str, str] = {}
    for name, url in raw_pairs:
        by_name.setdefault(name, url)

    seen_ids: set[str] = set()
    items: list[dict] = []
    for name, url in sorted(by_name.items(), key=lambda x: x[0]):
        base_id = f"dtail_{slugify(name)}"
        item_id = base_id
        suffix = 2
        while item_id in seen_ids:
            item_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_ids.add(item_id)

        items.append(
            {
                "id": item_id,
                "name": name,
                "category": CATEGORY,
                "url": BASE_URL,
                "image": url,
                "images": [url],
            }
        )

    print(f"[scrape_dtail] найдено {len(items)} декоров", file=sys.stderr)
    return items


if __name__ == "__main__":
    print(json.dumps(scrape_all(), ensure_ascii=False, indent=2))
