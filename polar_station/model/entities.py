"""Классы предметной области полярной станции.

Каждая сущность валидирует себя при создании, поэтому некорректный объект
невозможно получить ни из интерфейса, ни из хранилища.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional

from .errors import ValidationError
from .validation import (parse_date, parse_datetime, parse_enum, require_number,
                         require_text)

# ----------------------------------------------------------------- справочники


class Specialty(str, Enum):
    GLACIOLOGIST = "гляциолог"
    METEOROLOGIST = "метеоролог"
    RADIO_OPERATOR = "радист"
    MECHANIC = "механик"
    DOCTOR = "врач"


class Health(str, Enum):
    FIT = "годен"
    LIMITED = "ограниченно годен"
    UNFIT = "не годен"


class ResourceCategory(str, Enum):
    FUEL = "топливо"
    FOOD = "продовольствие"
    MEDICINE = "медикаменты"


class RequestStatus(str, Enum):
    CREATED = "создана"
    APPROVED = "утверждена"
    REJECTED = "отклонена"
    FULFILLED = "выполнена"


class IncidentKind(str, Enum):
    STORM = "шторм"
    BLIZZARD = "пурга"
    ICE_DRIFT = "ледовый дрейф"


# Минимальный состав смены по специальностям (используется в отчёте об укомплектованности).
REQUIRED_CREW = {
    Specialty.GLACIOLOGIST: 1,
    Specialty.METEOROLOGIST: 1,
    Specialty.RADIO_OPERATOR: 1,
    Specialty.MECHANIC: 2,
    Specialty.DOCTOR: 1,
}

SERVICE_INTERVAL_MOTOHOURS = 250
MIN_SHIFT_DAYS = 56   # ~2 месяца
MAX_SHIFT_DAYS = 95   # ~3 месяца

# ------------------------------------------------------------- виды измерений


class MeasurementKind:
    """Базовый вид наблюдения: код, единица измерения и допустимый диапазон."""
    code = ""
    title = ""
    unit = ""
    min_value = 0.0
    max_value = 0.0

    def validate(self, value) -> float:
        return float(require_number(value, self.title, self.min_value, self.max_value))


class AirTemperature(MeasurementKind):
    code, title, unit = "air_temp", "Температура воздуха", "°C"
    min_value, max_value = -90.0, 45.0


class AirHumidity(MeasurementKind):
    code, title, unit = "humidity", "Влажность воздуха", "%"
    min_value, max_value = 0.0, 100.0


class WindSpeed(MeasurementKind):
    code, title, unit = "wind_speed", "Скорость ветра", "м/с"
    min_value, max_value = 0.0, 90.0


class WindDirection(MeasurementKind):
    code, title, unit = "wind_dir", "Направление ветра", "°"
    min_value, max_value = 0.0, 360.0


class SnowDepth(MeasurementKind):
    code, title, unit = "snow_depth", "Толщина снежного покрова", "см"
    min_value, max_value = 0.0, 1000.0


class SeaSalinity(MeasurementKind):
    code, title, unit = "salinity", "Солёность морской воды", "‰"
    min_value, max_value = 0.0, 45.0


class SeaTemperature(MeasurementKind):
    code, title, unit = "water_temp", "Температура морской воды", "°C"
    min_value, max_value = -2.5, 35.0


class IceReconnaissance(MeasurementKind):
    """Ледовая разведка: сплочённость льда в баллах — только целые значения."""
    code, title, unit = "ice", "Ледовая разведка (сплочённость)", "баллы"
    min_value, max_value = 0.0, 10.0

    def validate(self, value) -> float:
        return float(require_number(value, self.title, self.min_value,
                                    self.max_value, integer=True))


MEASUREMENT_KINDS = {k.code: k for k in (
    AirTemperature(), AirHumidity(), WindSpeed(), WindDirection(),
    SnowDepth(), SeaSalinity(), SeaTemperature(), IceReconnaissance())}


def get_kind(code: str) -> MeasurementKind:
    try:
        return MEASUREMENT_KINDS[str(code).strip()]
    except KeyError:
        raise ValidationError("Неизвестный вид измерения") from None


# ------------------------------------------------------------------- сущности


@dataclass
class Shift:
    name: str
    start_date: date
    end_date: date
    id: Optional[int] = None

    def __post_init__(self):
        self.name = require_text(self.name, "Название смены", 60)
        self.start_date = parse_date(self.start_date, "Начало смены")
        self.end_date = parse_date(self.end_date, "Окончание смены")
        days = (self.end_date - self.start_date).days
        if not MIN_SHIFT_DAYS <= days <= MAX_SHIFT_DAYS:
            raise ValidationError(
                f"Длительность смены должна быть {MIN_SHIFT_DAYS}–{MAX_SHIFT_DAYS} дней "
                f"(ротация раз в 2–3 месяца), указано: {days}")

    def is_active(self, on: date) -> bool:
        return self.start_date <= on <= self.end_date


@dataclass
class Employee:
    full_name: str
    specialty: Specialty
    qualification: int
    arrival_date: date
    health: Health
    shift_id: int
    id: Optional[int] = None

    def __post_init__(self):
        self.full_name = require_text(self.full_name, "ФИО", 100)
        self.specialty = parse_enum(Specialty, self.specialty, "Специальность")
        self.qualification = require_number(self.qualification, "Уровень квалификации",
                                            1, 5, integer=True)
        self.arrival_date = parse_date(self.arrival_date, "Дата прибытия")
        self.health = parse_enum(Health, self.health, "Состояние здоровья")


@dataclass
class Instrument:
    name: str
    kind_code: str
    last_calibration: date
    interval_days: int
    id: Optional[int] = None

    def __post_init__(self):
        self.name = require_text(self.name, "Название прибора", 80)
        self.kind_code = get_kind(self.kind_code).code
        self.last_calibration = parse_date(self.last_calibration, "Дата калибровки")
        self.interval_days = require_number(self.interval_days, "Межкалибровочный интервал",
                                            1, 730, integer=True)

    @property
    def due_date(self) -> date:
        return self.last_calibration + timedelta(days=self.interval_days)

    def is_calibrated(self, on: date) -> bool:
        """Калибровка действует до due_date включительно; после — измерения блокируются."""
        return on <= self.due_date


@dataclass
class Resource:
    name: str
    category: ResourceCategory
    unit: str
    quantity: float
    min_norm: float
    id: Optional[int] = None

    def __post_init__(self):
        self.name = require_text(self.name, "Название ресурса", 80)
        self.category = parse_enum(ResourceCategory, self.category, "Категория")
        self.unit = require_text(self.unit, "Единица измерения", 20)
        self.quantity = float(require_number(self.quantity, "Остаток", 0))
        self.min_norm = float(require_number(self.min_norm, "Норма остатка", 0))

    @property
    def below_norm(self) -> bool:
        return self.quantity < self.min_norm

    @property
    def restock_amount(self) -> float:
        """Заявка пополняет запас до двойной нормы."""
        return round(self.min_norm * 2 - self.quantity, 3)


@dataclass
class SupplyRequest:
    resource_id: int
    quantity: float
    status: RequestStatus
    created_at: datetime
    decided_at: Optional[datetime] = None
    id: Optional[int] = None

    def __post_init__(self):
        self.quantity = float(require_number(self.quantity, "Количество в заявке", 0,
                                             min_exclusive=True))
        self.status = parse_enum(RequestStatus, self.status, "Статус заявки")
        self.created_at = parse_datetime(self.created_at, "Дата заявки")
        if self.decided_at is not None:
            self.decided_at = parse_datetime(self.decided_at, "Дата решения")


@dataclass
class Generator:
    name: str
    motohours: float
    last_service_mh: float
    id: Optional[int] = None

    def __post_init__(self):
        self.name = require_text(self.name, "Название генератора", 60)
        self.motohours = float(require_number(self.motohours, "Моточасы", 0))
        self.last_service_mh = float(require_number(self.last_service_mh,
                                                    "Моточасы последнего ТО", 0))
        if self.last_service_mh > self.motohours:
            raise ValidationError("Моточасы последнего ТО не могут превышать общую наработку")

    @property
    def hours_to_service(self) -> float:
        return round(SERVICE_INTERVAL_MOTOHOURS - (self.motohours - self.last_service_mh), 2)

    @property
    def needs_service(self) -> bool:
        return self.hours_to_service <= 0


@dataclass
class Incident:
    kind: IncidentKind
    occurred_at: datetime
    description: str
    measures_taken: str
    id: Optional[int] = None

    def __post_init__(self):
        self.kind = parse_enum(IncidentKind, self.kind, "Тип события")
        self.occurred_at = parse_datetime(self.occurred_at, "Время события")
        self.description = require_text(self.description, "Характер события", 300)
        self.measures_taken = require_text(self.measures_taken, "Принятые меры", 300)
