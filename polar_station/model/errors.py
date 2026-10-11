"""Исключения слоя Model. Controller превращает их в понятные сообщения для View."""


class StationError(Exception):
    """Базовая ошибка предметной области."""


class ValidationError(StationError):
    """Некорректные входные данные (пустое поле, значение вне диапазона)."""


class BusinessRuleError(StationError):
    """Нарушено бизнес-правило (прибор не откалиброван, остаток меньше расхода и т. д.)."""


class AccessDeniedError(StationError):
    """У роли нет права на действие."""


class NotFoundError(StationError):
    """Запрошенная запись не найдена."""
