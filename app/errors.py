from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


FIELD_LABELS = {
    "body": "Данные запроса",

    # Авторизация и профиль
    "phone_number": "Номер телефона",
    "password": "Пароль",
    "name": "Имя",
    "cookie.refresh_token": "Токен обновления сессии",

    # Товары, категории и фотографии
    "product_id": "Идентификатор товара",
    "category_id": "Идентификатор категории",
    "title": "Название",
    "price": "Цена",
    "count": "Количество товаров в наличии",
    "is_show": "Видимость товара",
    "is_show_case": "Показ товара на витрине",
    "compounds": "Состав товара",
    "compounds.*": "Позиция состава",
    "compounds.*.title": "Название позиции состава",
    "compounds.*.quantity": "Количество в позиции состава",
    "image_paths": "Фотографии товара",
    "image_paths.*": "Идентификатор фотографии",
    "image_urls": "Список идентификаторов фотографий",
    "image_urls.*": "Идентификатор фотографии",
    "description": "Описание",
    "photo_id": "Идентификатор фотографии",
    "photo": "Фотографии для загрузки",
    "photo.*": "Файл фотографии",

    # Заказы
    "order_id": "Идентификатор заказа",
    "items": "Позиции заказа",
    "items.*": "Позиция заказа",
    "items.*.product_id": "Идентификатор товара в заказе",
    "items.*.quantity": "Количество товара в заказе",
    "customer_name": "Имя покупателя",
    "customer_phone": "Телефон покупателя",
    "customer_email": "Электронная почта покупателя",
    "recipient_name": "Имя получателя",
    "recipient_phone": "Телефон получателя",
    "delivery_method": "Способ получения заказа",
    "delivery_date": "Дата доставки",
    "delivery_time_start": "Время начала доставки",
    "delivery_time_end": "Время окончания доставки",
    "shipping_address": "Адрес доставки",
    "comment": "Комментарий к заказу",

    # Поиск, фильтры и пагинация
    "page": "Номер страницы",
    "perPage": "Количество элементов на странице",
    "per_page": "Количество элементов на странице",
    "search": "Поисковая строка",
    "string": "Поисковая строка",
    "min_price": "Минимальная цена",
    "max_price": "Максимальная цена",
    "sort": "Сортировка",
    "role": "Роль пользователя",
    "is_ready": "Готовность товара",
    "is_not_show": "Фильтр скрытых товаров",
}

ERROR_MESSAGES = {
    "missing": "{label} — обязательное поле",
    "string_type": "{label} — ожидается строка",
    "string_too_short": "{label} — минимум {min_length} симв.",
    "string_too_long": "{label} — максимум {max_length} симв.",
    "string_pattern_mismatch": "{label} — неверный формат",
    "int_type": "{label} — ожидается целое число",
    "int_parsing": "{label} — ожидается целое число",
    "int_from_float": "{label} — ожидается целое число",
    "int_parsing_size": "{label} — слишком большое число",
    "decimal_type": "{label} — ожидается число",
    "decimal_parsing": "{label} — ожидается число",
    "decimal_max_digits": "{label} — максимум цифр: {max_digits}",
    "decimal_max_places": "{label} — максимум знаков после запятой: {decimal_places}",
    "decimal_whole_digits": "{label} — максимум цифр до запятой: {whole_digits}",
    "finite_number": "{label} — ожидается конечное число",
    "greater_than": "{label} — значение должно быть больше {gt}",
    "greater_than_equal": "{label} — значение должно быть не меньше {ge}",
    "less_than": "{label} — значение должно быть меньше {lt}",
    "less_than_equal": "{label} — значение должно быть не больше {le}",
    "bool_type": "{label} — ожидается true или false",
    "bool_parsing": "{label} — ожидается true или false",
    "list_type": "{label} — ожидается список",
    "too_short": "{label} — минимум элементов: {min_length}",
    "too_long": "{label} — максимум элементов: {max_length}",
    "uuid_type": "{label} — ожидается UUID",
    "uuid_parsing": "{label} — неверный формат UUID",
    "date_type": "{label} — укажите дату в формате ГГГГ-ММ-ДД",
    "date_parsing": "{label} — укажите дату в формате ГГГГ-ММ-ДД",
    "date_from_datetime_parsing": "{label} — укажите дату в формате ГГГГ-ММ-ДД",
    "date_from_datetime_inexact": "{label} — укажите дату без времени",
    "time_type": "{label} — укажите время в формате ЧЧ:ММ",
    "time_parsing": "{label} — укажите время в формате ЧЧ:ММ",
    "literal_error": "{label} — недопустимое значение",
    "enum": "{label} — недопустимое значение",
    "extra_forbidden": "Поле «{label}» не поддерживается",
    "model_type": "{label} — ожидается объект",
    "model_attributes_type": "{label} — ожидается объект",
    "json_invalid": "Некорректный JSON в теле запроса",
}

PHONE_FORMAT_MESSAGE = "Введите номер телефона в формате +79991234567"

VALIDATION_MESSAGES = {
    ("phone_number", "string_pattern_mismatch"): PHONE_FORMAT_MESSAGE,
    ("customer_phone", "string_pattern_mismatch"): PHONE_FORMAT_MESSAGE,
    ("recipient_phone", "string_pattern_mismatch"): PHONE_FORMAT_MESSAGE,
    ("customer_email", "value_error"): "Введите корректный адрес электронной почты",
    ("delivery_method", "enum"): "Выберите доставку (delivery) или самовывоз (pickup)",
    ("role", "enum"): "Допустимые роли: customer, manager, admin",
    ("photo.*", "value_error"): "Загрузите файл фотографии",
}


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = []

    for error in exc.errors():
        location = error["loc"]
        source = location[0] if location else "request"
        field_parts = (
            location[1:]
            if location and location[0] in {"body", "query", "path", "header"}
            else location
        )
        field = ".".join(map(str, field_parts)) or source

        field_key = ".".join("*" if isinstance(part, int)
                              else str(part)for part in field_parts) or field

        error_type = error["type"]
        context = error.get("ctx") or {}
        label = FIELD_LABELS.get(field_key, field)

        message = VALIDATION_MESSAGES.get((field_key, error_type))

        if message is None:
            if error_type == "request_value_invalid":
                message = error["msg"]
            else:
                template = ERROR_MESSAGES.get(error_type, "Проверьте значение поля «{label}»")
                message = template.format(label=label, **context)
        errors.append({"field": field, "message": message})

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )   