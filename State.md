# State — handoff для следующих чатов

Читать **первым делом** перед любыми правками. Краткий контекст проекта em-c-catalog-bot.

---

## Проект

Telegram WebApp-каталог листовых материалов (ЛДСП, столешницы, HPL, плёнка, ткани, камень, RAL).  
Данные: `data/materials.json` + локальные фото `data/images/{site}/{id}/`.  
Фронт: один файл `index.html` (GitHub Pages). Бренд: **NeoModern**.

**Репозиторий:** https://github.com/ghostvip1717-glitch/em-c-catalog-bot.git  
**Локальный путь:** `/Users/aleksandr/Desktop/Claude/Кодинг-проекты/kursor`  
⚠️ Путь с кириллицей (`ВайбКодинг/kursor`) ломает Shell/Glob — не использовать.

---

## Правила работы (от владельца)

- Сначала изучить код, не дублировать функциональность, не ломать существующее.
- Без костылей и запасных вариантов — один продакшн-путь.
- **Коммит / push** — только по явной просьбе пользователя.
- Перед важными шагами — спросить; сервисы в отдельных терминалах.
- Не удалять данные в БД; не коммитить секреты, `.DS_Store`, `*.bak`, временный мусор.
- Важные события — кратко сюда в `State.md`.

---

## Что уже сделано (2026-07-10)

### HPL dtail.kz
- Скрапер: `scraper/scrape_dtail.py` — **requests + Creatium `delivery-builder?action=async`**, Playwright **не нужен**.
- Источник: https://dtail.kz/HPL-2 → ~132 декора.
- Категория в JSON: **`HPL (Dtail)`** (слово «Панели» **не использовать**).
- ID: префикс `dtail_` → фото в `data/images/dtail/`.
- Интеграция: `scraper/scrape.py` (`import scrape_dtail`, `site_of` → `dtail`, `ids_by_site.dtail`).

### Навигация (`index.html`)
- Группировка по типу материала (`siteGroupOf`), иконки: `SITE_ORDER`.
- **HPL (Dtail)** под иконкой **«Столешницы»** (`stoleshnitsy`), не отдельная иконка.
- Подсекции в popover/шторке (`SITE_POPOVER_SUBGROUPS`):
  - **Столешницы:** Россия, Австрия (Egger)
  - **HPL (Dtail)** — отдельная подсекция
  - **ЛДСП:** Россия / Австрия (Egger)
- **Плёнка** — без изменений (Kira + Adilet в одной иконке).
- Legacy: старая категория `Панели: HPL (Dtail)` в subgroup rules — до полного перескрапа.

### Бренд NeoModern
- Splash: `splash-top-label`.
- Шапка: между кнопкой «Все материалы» и рядом иконок — `.top-brand-wrap` (полоски + **NeoModern**).

### CI
- `.github/workflows/update-catalog.yml`: `checkout@v5`, `setup-python@v6`, `pip install requests beautifulsoup4 Pillow`.
- После правок скрапера: `gh workflow run update-catalog.yml` (по запросу).
- Push workflow-файлов требует `gh auth` scope **workflow**.

---

## Файлы — что смотреть

| Файл | Зачем |
|------|--------|
| `State.md` | Этот handoff |
| `index.html` | UI, `siteGroupOf`, `SITE_POPOVER_SUBGROUPS`, `SITE_ORDER`, фильтры, NeoModern |
| `scraper/scrape.py` | Оркестратор всех источников |
| `scraper/scrape_dtail.py` | HPL dtail |
| `scraper/scrape_profikz.py` | Egger ЛДСП/столешницы |
| `scraper/scrape_adilet.py`, `scrape_kira.py`, `scrape_interstone.py` | Остальные источники |
| `scraper/image_utils.py` | Скачивание/WebP, `data/images/` |
| `data/materials.json` | Каталог (большой; grep по категориям/id) |
| `.github/workflows/update-catalog.yml` | Автообновление каталога |

Источники и префиксы id → папка images: `emc`, `adilet`, `kira`, `interstone`, `profikz`, **`dtail`**.

---

## Категории в materials.json (актуальные)

- `ЛДСП: Россия`, `ЛДСП: Австрия (Egger)`
- `Столешницы: Россия`, `Столешницы: Австрия (Egger)`
- **`HPL (Dtail)`** — 132 позиции
- `ПВХ плёнка: …` (Wood, Texture, KIRA …, Solid Color)
- `Ткани: …`, `Акриловый/Кварцевый камень`, `Краски RAL Classic`

---

## Отложено (не трогать без запроса)

- Улучшение фильтров: чип «сбросить», упрощение трёх входов (кнопка / иконки / шторка ☰).
- Разделение Kira vs Adilet в плёнке — пользователь просил **оставить как есть**.

## Уведомления Владимиру (2026-07-10, в работе)

- Worker: `https://tight-firefly-8060.ghostvip1717.workers.dev` — **работает** (2026-07-10). CHAT_ID тест: `2026940090`; Владимир: `/start` @NeoModern_Bot → свой id.
- `index.html`: RAL fix — fullBleedHole шаг 3, purge backdrops, html.tutorial-active off.
- `CHAT_ID=2026940090`, `API_SECRET=neo_7fK2mQx9pL4wR8`, бот @NeoModern_Bot.
- Wrangler: `wrangler.toml` + `notify-worker.js` (env); деплой нужен `CLOUDFLARE_API_TOKEN`.

---

## Типовые команды

```bash
cd "/Users/aleksandr/Desktop/Claude/Кодинг-проекты/kursor"
.venv/bin/python scraper/scrape_dtail.py   # тест dtail (~132)
.venv/bin/python scraper/scrape.py         # полный скрап локально
gh workflow run update-catalog.yml         # обновить JSON + фото на GitHub
```

---

## Последние коммиты (ориентир)

- `3b97872` NeoModern между «Все материалы» и иконками
- `037f95b` HPL (Dtail) под столешницами + подсекции
- `4fedf9d` / scrape_dtail — первый скрапер dtail
- `b1a613e` Actions Node 24 (checkout@v5, setup-python@v6)
