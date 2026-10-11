"""Роли, права доступа и хеширование паролей.

Проверка прав выполняется в сервисах Model (AccessPolicy.require), поэтому обход
меню во View/Controller не даёт доступа к операциям.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .errors import AccessDeniedError, ValidationError

PBKDF2_ITERATIONS = 200_000


class Role(str, Enum):
    MANAGER = "руководитель"
    OBSERVER = "наблюдатель"
    ENGINEER = "инженер"


class Permission(Enum):
    VIEW = auto()
    MANAGE_STAFF = auto()
    RECORD_MEASUREMENT = auto()
    CALIBRATE = auto()
    CONSUME_RESOURCE = auto()
    APPROVE_REQUEST = auto()
    RECEIVE_SUPPLY = auto()
    LOG_GENERATOR = auto()
    SERVICE_GENERATOR = auto()
    LOG_INCIDENT = auto()
    VIEW_REPORTS = auto()


_ROLE_PERMISSIONS = {
    Role.MANAGER: set(Permission),
    Role.OBSERVER: {Permission.VIEW, Permission.RECORD_MEASUREMENT, Permission.LOG_INCIDENT},
    Role.ENGINEER: {Permission.VIEW, Permission.CALIBRATE, Permission.CONSUME_RESOURCE,
                    Permission.RECEIVE_SUPPLY, Permission.LOG_GENERATOR,
                    Permission.SERVICE_GENERATOR, Permission.LOG_INCIDENT},
}


@dataclass(frozen=True)
class Actor:
    """Вошедший пользователь (контекст выполнения операции)."""
    user_id: int
    username: str
    role: Role
    employee_id: Optional[int] = None


class AccessPolicy:
    @staticmethod
    def can(role: Role, permission: Permission) -> bool:
        return permission in _ROLE_PERMISSIONS[role]

    @staticmethod
    def require(actor: Actor, permission: Permission) -> None:
        if actor is None or not AccessPolicy.can(actor.role, permission):
            raise AccessDeniedError("Недостаточно прав для выполнения операции")


def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 6:
        raise ValidationError("Пароль должен содержать не менее 6 символов")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt_hex), PBKDF2_ITERATIONS)
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)
