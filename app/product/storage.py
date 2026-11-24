import re
import shutil
import time
import uuid
from pathlib import Path
from uuid import UUID
import logging

TMP_DIR = Path("uploads/tmp")
PRODUCT_DIR = Path("uploads/product")
CATEGORY_DIR = Path("uploads/category")

# Для доступа к уже сохранённым фотографиям.
LEGACY_DIR = Path("uploads/products")

ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_SIZE = 5 * 1024 * 1024
TMP_TTL = 60 * 30
MAX_FILES = 5

ID_RE = re.compile(r"^[0-9a-f]{32}(?:\.(?:jpg|png|webp))?$")

for directory in (TMP_DIR, PRODUCT_DIR, CATEGORY_DIR, LEGACY_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def save_tmp(content: bytes, content_type: str) -> str:
    filename = f"{uuid.uuid4().hex}{ALLOWED_TYPES[content_type]}"
    (TMP_DIR / filename).write_bytes(content)
    return  f"/files/tmp/{filename}"

def photo_path(image_url: str) -> Path:
    """Получить локальный путь по URL фотографии."""
    if image_url.startswith("/files/product/"):
        root = PRODUCT_DIR
        relative = image_url[len("/files/product/"):]

    elif image_url.startswith("/files/category/"):
        root = CATEGORY_DIR
        relative = image_url[len("/files/category/"):]

    elif image_url.startswith("/files/tmp/"):
        root = TMP_DIR
        relative = image_url[len("/files/tmp/"):]

    else:
        raise ValueError("Некорректная ссылка на фотографию")

    root = root.resolve()
    path = (root / relative).resolve()

    if path == root or not path.is_relative_to(root):
        raise ValueError("Некорректный путь фотографии")

    return path


def remove_empty_product_dir(directory: Path) -> None:
    # Удалять можно только непосредственную подпапку PRODUCT_DIR.
    if directory.resolve().parent != PRODUCT_DIR.resolve():
        return

    try:
        directory.rmdir()
    except OSError:
        # Папка не пуста либо уже удалена.
        pass


def rollback_move(moved: list[tuple[Path, Path]]) -> None:
    for src, dst in reversed(moved):
        if dst.is_file():
            shutil.move(str(dst), str(src))
            remove_empty_product_dir(dst.parent)


def rollback_photos(image_urls: list[str]) -> None:
    """Вернуть фотографии в tmp при ошибке сохранения в БД."""
    for image_url in image_urls:
        src = photo_path(image_url)

        if src.is_file():
            shutil.move(str(src), str(TMP_DIR / src.name))
            remove_empty_product_dir(src.parent)


def commit_tmp(
    upload_ids: list[str],
    *,
    product_id: UUID | None = None,
) -> list[str]:
    if product_id is None:
        target_dir = CATEGORY_DIR
        url_prefix = "/files/category"
    else:
        product_id = UUID(str(product_id))
        target_dir = PRODUCT_DIR / str(product_id)
        url_prefix = f"/files/product/{product_id}"

    moved: list[tuple[Path, Path]] = []

    try:
        for upload_id in upload_ids:
            if not ID_RE.fullmatch(upload_id):
                raise ValueError("Некорректный идентификатор загруженного файла")

            if Path(upload_id).suffix:
                src = TMP_DIR / upload_id
            else:
                src = next(
                    (
                        TMP_DIR / f"{upload_id}{ext}"
                        for ext in ALLOWED_TYPES.values()
                        if (TMP_DIR / f"{upload_id}{ext}").is_file()
                    ),
                    None,
                )

            if src is None or not src.is_file():
                raise FileNotFoundError(upload_id)

            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / src.name

            if dst.exists():
                raise FileExistsError(dst)

            shutil.move(str(src), str(dst))
            moved.append((src, dst))

    except Exception:
        rollback_move(moved)
        remove_empty_product_dir(target_dir)
        raise

    return [
        f"{url_prefix}/{dst.name}"
        for _, dst in moved
    ]


def cleanup_tmp() -> None:
    now = time.time()

    for file in TMP_DIR.iterdir():
        try:
            if file.is_symlink() or not file.is_file():
                continue
            if now - file.stat().st_mtime >= TMP_TTL:
                file.unlink(missing_ok=True)
        except FileNotFoundError:
            # Файл уже переместили или удалили.
            continue
        except OSError:
            logging.getLogger(__name__).exception(
                "Не удалось удалить временный файл: %s", file
            )

def unlink_photo(image_url: str) -> None:
    path = photo_path(image_url)
    path.unlink(missing_ok=True)
    remove_empty_product_dir(path.parent)


def delete_photo(image_url: str | None) -> None:
    if not image_url:
        return

    try:
        unlink_photo(image_url)
    except ValueError:
        return
    except OSError:
        logging.getLogger(__name__).exception(
            "Не удалось удалить фото %s", image_url
        )


