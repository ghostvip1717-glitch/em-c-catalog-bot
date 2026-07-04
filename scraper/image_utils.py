#!/usr/bin/env python3
"""
Общие функции скачивания и сжатия фото товаров для локального хостинга.

Раньше materials.json хранил прямые внешние ссылки на фото (em-c.kz,
adilet.net, interstone.kz) — приложение грузило их напрямую с чужих серверов
в оригинальном (тяжёлом) размере. Теперь каждый скрапер прогоняет свои фото
через этот модуль: фото скачивается один раз, сжимается в WebP и режется на
две версии — маленькое превью для сетки карточек и версия побольше для
полноэкранного просмотрщика. Готовые файлы кладутся в data/images/ и
коммитятся в репозиторий вместе с materials.json, поэтому дальше отдаются
через GitHub Pages (свой CDN), а не через 3 внешних сайта.

Работает инкрементально: если файл для товара уже скачан на диске — повторно
не скачивается и не пережимается. Это важно, потому что workflow гоняется
каждый день по расписанию, а подавляющее большинство фото между запусками
не меняется.
"""

import io
import shutil
import sys
from pathlib import Path

import requests
from PIL import Image

IMAGES_ROOT = Path(__file__).resolve().parent.parent / "data" / "images"

THUMB_SIZE = (400, 400)   # превью в сетке карточек каталога
FULL_SIZE = (1200, 1200)  # версия для полноэкранного просмотрщика (свайп-галерея)
WEBP_QUALITY = 82

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def _resize_contain(img: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    """Уменьшает изображение так, чтобы оно вписалось в max_size, сохраняя пропорции."""
    resized = img.copy()
    resized.thumbnail(max_size, Image.LANCZOS)
    return resized


def _save_webp(img: Image.Image, path: Path, quality: int = WEBP_QUALITY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    img.save(path, "WEBP", quality=quality, method=6)


def thumb_path_for(full_rel_path: str) -> str:
    """data/images/site/id/1.webp -> data/images/site/id/1_thumb.webp"""
    p = Path(full_rel_path)
    return str(p.parent / f"{p.stem}_thumb{p.suffix}")


def download_item_images(site: str, item_id: str, urls: list[str]) -> list[str]:
    """
    Скачивает и сохраняет фото товара локально (полная версия + превью для
    каждого фото). Возвращает список ОТНОСИТЕЛЬНЫХ (от корня репозитория)
    путей к полноразмерным версиям — их же кладём в поле "images" в
    materials.json; путь до превью получается через thumb_path_for().

    Если для конкретного фото уже есть оба локальных файла — скачивание
    пропускается (см. докстринг модуля про инкрементальность).
    """
    result_paths: list[str] = []
    item_dir = IMAGES_ROOT / site / item_id

    for idx, url in enumerate(urls, start=1):
        if not url:
            continue
        full_path = item_dir / f"{idx}.webp"
        thumb_path = item_dir / f"{idx}_thumb.webp"
        rel_full = f"data/images/{site}/{item_id}/{idx}.webp"

        if full_path.exists() and thumb_path.exists():
            result_paths.append(rel_full)
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            img.load()
        except Exception as exc:  # noqa: BLE001 - одно упавшее фото не должно рушить весь скрапинг
            print(f"[image_utils] не удалось скачать {url}: {exc}", file=sys.stderr)
            continue

        try:
            _save_webp(_resize_contain(img, FULL_SIZE), full_path)
            _save_webp(_resize_contain(img, THUMB_SIZE), thumb_path)
        except Exception as exc:  # noqa: BLE001
            print(f"[image_utils] не удалось сохранить {url}: {exc}", file=sys.stderr)
            continue

        result_paths.append(rel_full)

    return result_paths


def process_item_images(item: dict, site: str) -> dict:
    """
    Заменяет внешние ссылки на фото товара (поля "image"/"images") локальными
    путями к скачанным и сжатым файлам. Добавляет поле "thumb" — путь к
    маленькому превью, которое фронтенд использует в сетке карточек, чтобы
    не тянуть полноразмерное фото там, где нужна только миниатюра.

    Если скачать фото не удалось (сеть недоступна, сайт лёг и т.п.) — не
    теряем фото полностью, а оставляем оригинальную внешнюю ссылку как есть,
    чтобы приложение продолжило показывать хоть что-то.
    """
    raw_images = item.get("images") if isinstance(item.get("images"), list) else []
    if not raw_images and item.get("image"):
        raw_images = [item["image"]]
    raw_images = [u for u in raw_images if u]

    if not raw_images:
        item["thumb"] = None
        item["thumbs"] = []
        item["images"] = []
        item["image"] = None
        return item

    local_paths = download_item_images(site, item["id"], raw_images)

    if not local_paths:
        # Скачивание не удалось ни для одного фото — фолбэк на внешние ссылки.
        item["images"] = raw_images
        item["thumbs"] = raw_images
        item["thumb"] = raw_images[0]
        item["image"] = raw_images[0]
        return item

    # "thumbs" — превью ПО КАЖДОМУ фото (не только по первому), нужно фронтенду
    # для blur-up эффекта в полноэкранном просмотрщике: пока грузится полный
    # размер конкретного слайда, сразу показываем его собственное маленькое
    # (уже наверняка закэшированное) превью растянутым и размытым.
    item["images"] = local_paths
    item["thumbs"] = [thumb_path_for(p) for p in local_paths]
    item["thumb"] = item["thumbs"][0]
    item["image"] = local_paths[0]
    return item


def cleanup_orphans(current_ids_by_site: dict[str, set]) -> None:
    """
    Удаляет папки с фото товаров, которых больше нет в свежем каталоге
    (сняты с продажи у источника и т.п.), чтобы data/images/ не разрасталась
    бесконечно мусором от старых товаров.
    """
    if not IMAGES_ROOT.exists():
        return
    for site_dir in IMAGES_ROOT.iterdir():
        if not site_dir.is_dir():
            continue
        keep_ids = current_ids_by_site.get(site_dir.name, set())
        for item_dir in site_dir.iterdir():
            if item_dir.is_dir() and item_dir.name not in keep_ids:
                shutil.rmtree(item_dir)
                print(f"[image_utils] удалена папка сироты: {item_dir}", file=sys.stderr)
