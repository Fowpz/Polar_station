"""Функции серверной валидации. Используются сущностями и сервисами Model."""
import math
from datetime import date, datetime

from .errors import ValidationError

DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M"


def require_text(value, field: str, max_len: int = 120) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Поле «{field}» обязательно для заполнения")
    text = " ".join(value.split())
    if len(text) > max_len:
        raise ValidationError(f"Поле «{field}» длиннее {max_len} символов")
    return text


def require_number(value, field: str, min_value=None, max_value=None,
                   integer: bool = False, min_exclusive: bool = False):
    if isinstance(value, bool):
        raise ValidationError(f"Поле «{field}» должно быть числом")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"Поле «{field}» должно быть числом") from None
    if math.isnan(number) or math.isinf(number):
        raise ValidationError(f"Поле «{field}» содержит недопустимое число")
    if integer and number != int(number):
        raise ValidationError(f"Поле «{field}» должно быть целым числом")
    if min_value is not None:
        if number < min_value or (min_exclusive and number == min_value):
            sign = ">" if min_exclusive else "≥"
            raise ValidationError(f"Поле «{field}» должно быть {sign} {min_value}")
    if max_value is not None and number > max_value:
        raise ValidationError(f"Поле «{field}» должно быть ≤ {max_value}")
    return int(number) if integer else number


def parse_date(value, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value).strip(), DATE_FMT).date()
    except ValueError:
        raise ValidationError(f"Поле «{field}»: ожидается дата ГГГГ-ММ-ДД") from None


def parse_datetime(value, field: str) -> datetime:
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0)
    text = str(value).strip().replace("T", " ")
    try:
        return datetime.strptime(text, DATETIME_FMT)
    except ValueError:
        raise ValidationError(
            f"Поле «{field}»: ожидается дата и время ГГГГ-ММ-ДД ЧЧ:ММ") from None


def parse_enum(enum_cls, value, field: str):
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip().lower()
    for member in enum_cls:
        if text in (member.value.lower(), member.name.lower()):
            return member
    allowed = ", ".join(m.value for m in enum_cls)
    raise ValidationError(f"Поле «{field}»: допустимые значения — {allowed}")
