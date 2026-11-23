"""Import a Flowwow catalog export through the store API."""

import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

# Настройки импорта
SOURCE_DIR = Path(__file__).resolve().parent / "page"
CATEGORIES_FILE = "categories.json"
PRODUCT_FILES = ("page2.json", "page3.json", "page4.json")  # Можно указать несколько файлов в нужном порядке.
PRODUCT_LIMIT = 20  # Первые 20 подходящих товаров. None — все товары из выбранных файлов.
PHOTOS_PER_PRODUCT = 5  # От 0 до 5. Обложка новой категории загружается отдельно.
API_URL = "http://127.0.0.1:8000"
ACCESS_TOKEN = input("Вставь access token для импорта: ").strip()
APPLY = True  # False — предпросмотр, True — импорт.

MAX_FILES = 5
MAX_SIZE = 5 * 1024 * 1024
ID_RE = re.compile(r"[0-9a-f]{32}(?:\.(?:jpg|png|webp))?")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_catalog(directory, categories_file, product_files, product_limit, photos_per_product):
    source = read_json(directory / categories_file)
    shop_id = source["shopId"]
    category_names = {
        (category["categoryId"], subcategory["subCategoryId"]): subcategory["name"]
        for category in source["data"]
        for subcategory in category["subCategories"]
    }
    categories = {}
    products = {}
    compounds = {}
    skipped = Counter()
    for filename in product_files:
        path = directory / filename
        for item in read_json(path)["items"]:
            if item.get("isActive") is not True:
                skipped["inactive product"] += 1
                continue

            price = Decimal(item["price"])
            if item["currencyCode"] != "RUB":
                skipped["currency other than RUB"] += 1
                continue
            if not price.is_finite() or not 0 < price <= Decimal("9999999999.99"):
                skipped["invalid price"] += 1
                continue
            if price.quantize(Decimal("0.01")) != price:
                skipped["invalid price precision"] += 1
                continue

            product_id = uuid5(NAMESPACE_URL, f"https://flowwow.com/products/{item['productId']}")
            if product_id in products:
                skipped["duplicate product"] += 1
                continue

            if len(item["name"].strip()) < 5:
                skipped["title shorter than 5 characters"] += 1
                continue
            category_key = (item["categoryId"], item["subCategoryId"])
            if category_key not in category_names:
                raise ValueError(f"{path.name}: unknown category {category_key} for product {item['productId']}")
            parent_id, subcategory_id = category_key
            category_id = uuid5(
                NAMESPACE_URL, f"https://flowwow.com/shops/{shop_id}/categories/{parent_id}/{subcategory_id}"
            )
            images = item.get("images") or []
            category = categories.setdefault(category_id, {
                "id": category_id,
                "title": category_names[category_key][:20],
                "image_path": "",
            })
            if not category["image_path"] and images:
                category["image_path"] = images[0]

            count = item["stock"]
            products[product_id] = {
                "id": product_id,
                "category_id": category_id,
                "title": item["name"].strip()[:50],
                "price": price,
                "count": count,
                "is_show": count > 0 and not item["isArchived"],
                "is_show_case": False,
                "description": (item.get("description") or "")[:255],
                "image_paths": images[:photos_per_product],
            }
            composition = (item.get("properties") or {}).get("consist") or []
            compounds[product_id] = [
                {"title": part["name"][:16], "quantity": part["quantity"]}
                for part in composition
                if part["name"].strip() and 0 < part["quantity"] <= 2147483647
            ]

            if product_limit is not None and len(products) == product_limit:
                return categories, products, compounds, skipped

    return categories, products, compounds, skipped


def upload_photos(api, downloads, endpoint, urls):
    upload_ids = []
    for start in range(0, len(urls), MAX_FILES):
        files = []
        for url in urls[start:start + MAX_FILES]:
            parsed = urlsplit(url)
            hostname = parsed.hostname or ""
            if parsed.scheme != "https" or not hostname.endswith(".flowwow-images.com"):
                raise ValueError(f"Unexpected Flowwow image URL: {url}")
            with downloads.stream("GET", url) as response:
                response.raise_for_status()
                content = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    content.extend(chunk)
                    if len(content) > MAX_SIZE:
                        raise ValueError(f"Image exceeds the upload limit: {url}")
                content_type = response.headers.get("content-type", "application/octet-stream")
            files.append(("photo", (Path(parsed.path).name or "photo", bytes(content), content_type)))

        response = api.post(endpoint, files=files)
        response.raise_for_status()
        batch_ids = response.json()["upload_ids"]
        if len(batch_ids) != len(files) or any(not ID_RE.fullmatch(id_) for id_ in batch_ids):
            raise ValueError(f"Invalid upload response from {endpoint}")
        upload_ids.extend(batch_ids)
    return upload_ids


def existing_categories(api):
    categories = {}
    page = 1
    while True:
        response = api.get("categories/", params={"page": page, "per_page": 100})
        response.raise_for_status()
        result = response.json()
        for category in result["data"]:
            title = category["title"].strip().casefold()
            categories.setdefault(title, []).append(category["id"])
        if not result["meta"]["isNext"]:
            return categories
        page += 1


def import_catalog(categories, products, compounds, api_url, token, state_path):
    import httpx

    inserted = 0
    with (
        httpx.Client(base_url=api_url, headers={"Authorization": f"Bearer {token}"}, timeout=30) as api,
        httpx.Client(timeout=30) as downloads,
        closing(sqlite3.connect(state_path)) as state,
    ):
        state.execute(
            "CREATE TABLE IF NOT EXISTS imported ("
            "api_url TEXT NOT NULL, source_id TEXT NOT NULL, product_id TEXT NOT NULL, "
            "PRIMARY KEY (api_url, source_id))"
        )
        category_ids = existing_categories(api)
        for product_id, product in products.items():
            with state:
                state.execute("BEGIN IMMEDIATE")
                key = (api_url, str(product_id))
                if state.execute("SELECT 1 FROM imported WHERE api_url = ? AND source_id = ?", key).fetchone():
                    continue

                source = categories[product["category_id"]]
                title = source["title"].strip().casefold()
                matches = category_ids.get(title, [])
                if len(matches) > 1:
                    raise ValueError(f"Multiple existing categories named {source['title']!r}")
                if matches:
                    category_id = matches[0]
                else:
                    if not source["image_path"]:
                        raise ValueError(f"No cover image for category {source['title']!r}")
                    photo_id, = upload_photos(api, downloads, "categories/uploads", [source["image_path"]])
                    response = api.post("categories/", json={"title": source["title"], "image_path": photo_id})
                    response.raise_for_status()
                    category_id = response.json()["id"]
                    category_ids[title] = [category_id]

                upload_ids = upload_photos(api, downloads, "products/uploads", product["image_paths"])
                payload = {name: value for name, value in product.items() if name != "id"}
                payload.update(
                    category_id=category_id,
                    price=str(product["price"]),
                    image_paths=upload_ids,
                    compounds=compounds[product_id],
                )
                response = api.post("products/create", json=payload)
                response.raise_for_status()
                state.execute("INSERT INTO imported VALUES (?, ?, ?)", (*key, response.json()["id"]))
            inserted += 1
    return inserted


def main():
    if not PRODUCT_FILES:
        raise SystemExit("Укажи хотя бы один JSON с товарами в PRODUCT_FILES.")
    if PRODUCT_LIMIT is not None and (
        type(PRODUCT_LIMIT) is not int or PRODUCT_LIMIT < 1
    ):
        raise SystemExit("PRODUCT_LIMIT должен быть целым числом от 1 или None.")
    if type(PHOTOS_PER_PRODUCT) is not int or not 0 <= PHOTOS_PER_PRODUCT <= MAX_FILES:
        raise SystemExit("PHOTOS_PER_PRODUCT должен быть целым числом от 0 до 5.")
    token = ACCESS_TOKEN.strip()
    if APPLY and not token:
        raise SystemExit("Вставь access token в ACCESS_TOKEN.")

    directory = SOURCE_DIR.expanduser()
    try:
        categories, products, compounds, skipped = load_catalog(
            directory, CATEGORIES_FILE, PRODUCT_FILES, PRODUCT_LIMIT, PHOTOS_PER_PRODUCT
        )
    except (OSError, ValueError, KeyError, ArithmeticError) as error:
        raise SystemExit(f"Не удалось прочитать выгрузку: {error}") from error

    photo_count = sum(len(product["image_paths"]) for product in products.values())
    print(f"Товаров: {len(products)}, категорий: {len(categories)}, фото товаров: {photo_count}")
    print(f"Позиций состава: {sum(map(len, compounds.values()))}")
    for reason, count in sorted(skipped.items()):
        print(f"Пропущено ({reason}): {count}")

    if not APPLY:
        print("Предпросмотр. Для импорта поставь APPLY = True.")
        return

    state_path = directory / ".flowwow-seed.sqlite3"
    inserted = import_catalog(
        categories, products, compounds, API_URL.rstrip("/"), token, state_path
    )
    print(f"Создано товаров: {inserted}, ранее импортировано: {len(products) - inserted}")


if __name__ == "__main__":
    main()
