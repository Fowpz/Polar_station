"""Демо-данные для первого запуска (только если БД пустая)."""
from datetime import datetime, timedelta

from .database import Database
from .entities import (Employee, Generator, Instrument, Resource, Shift, RequestStatus)
from .repositories import (EmployeeRepository, GeneratorRepository, InstrumentRepository,
                           ResourceRepository, ShiftRepository, UserRepository)
from .security import Role, hash_password

DEMO_ACCOUNTS = [("boss", "boss123", "руководитель"),
                 ("observer", "observer123", "наблюдатель"),
                 ("engineer", "engineer123", "инженер")]


def seed_demo(db: Database, today: datetime = None) -> None:
    users = UserRepository(db)
    if users.count():
        return
    day = (today or datetime.now()).date()
    with db.tx():
        shift_id = ShiftRepository(db).add(
            Shift("Смена №12", day - timedelta(days=30), day + timedelta(days=45)))
        emp = EmployeeRepository(db)
        crew = [("Иванов Андрей Петрович", "гляциолог", 4, "годен"),
                ("Петрова Елена Сергеевна", "метеоролог", 5, "годен"),
                ("Сидоров Виктор Николаевич", "радист", 3, "годен"),
                ("Козлов Дмитрий Игоревич", "механик", 4, "годен"),
                ("Морозов Роман Алексеевич", "механик", 3, "ограниченно годен"),
                ("Белова Ольга Викторовна", "врач", 5, "годен")]
        ids = [emp.add(Employee(n, s, q, day - timedelta(days=30), h, shift_id))
               for n, s, q, h in crew]

        ins = InstrumentRepository(db)
        recent = day - timedelta(days=20)
        for name, kind, last, interval in [
                ("Термометр воздуха ТМ-1", "air_temp", recent, 180),
                ("Гигрометр ВИТ-2", "humidity", recent, 180),
                ("Анемометр М-63", "wind_speed", recent, 90),
                ("Флюгер Вильда", "wind_dir", recent, 365),
                ("Снегомерная рейка М-46", "snow_depth", recent, 365),
                # просрочена — демонстрирует блокировку измерений
                ("Солемер ГМ-65", "salinity", day - timedelta(days=200), 90),
                ("Термометр воды ТМ-3", "water_temp", recent, 180),
                ("Ледовая разведка (визуальная)", "ice", recent, 365)]:
            ins.add(Instrument(name, kind, last, interval))

        res = ResourceRepository(db)
        res.add(Resource("Дизельное топливо", "топливо", "л", 12000, 10000))
        res.add(Resource("Продовольствие", "продовольствие", "пайков", 900, 400))
        res.add(Resource("Медикаменты (аптечки)", "медикаменты", "наборов", 40, 15))

        gens = GeneratorRepository(db)
        gens.add(Generator("ДГ-1", 1180, 1000))
        gens.add(Generator("ДГ-2", 1260, 1000))   # 260 м/ч с ТО — требуется обслуживание

        users.add("boss", hash_password("boss123"), Role.MANAGER.value, None)
        users.add("observer", hash_password("observer123"), Role.OBSERVER.value, ids[1])
        users.add("engineer", hash_password("engineer123"), Role.ENGINEER.value, ids[3])
