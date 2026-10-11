"""Controller: принимает ввод из View, вызывает сервисы Model, показывает результат.
Ошибки Model не подавляются — превращаются в понятное сообщение во View."""
from datetime import datetime
from typing import Callable, List, NamedTuple, Optional

from model.entities import (Health, IncidentKind, MEASUREMENT_KINDS, Specialty)
from model.errors import AccessDeniedError, StationError
from model.security import Actor, AccessPolicy, Permission


class Action(NamedTuple):
    label: str
    permission: Permission
    handler: Callable


class Controller:
    def __init__(self, view, auth, staff, instruments, measurements, supply,
                 generators, incidents, reports):
        self.view = view
        self.auth, self.staff, self.instruments = auth, staff, instruments
        self.measurements, self.supply, self.generators = measurements, supply, generators
        self.incidents, self.reports = incidents, reports
        self.actor: Optional[Actor] = None
        self._actions: List[Action] = [
            Action("Смены и сотрудники", Permission.VIEW, self.show_staff),
            Action("Создать смену", Permission.MANAGE_STAFF, self.create_shift),
            Action("Зачислить сотрудника в смену", Permission.MANAGE_STAFF, self.register_employee),
            Action("Внести измерение", Permission.RECORD_MEASUREMENT, self.record_measurement),
            Action("Последние измерения", Permission.VIEW, self.show_measurements),
            Action("Приборы и калибровка", Permission.VIEW, self.show_instruments),
            Action("Провести калибровку прибора", Permission.CALIBRATE, self.calibrate),
            Action("Склад: остатки ресурсов", Permission.VIEW, self.show_resources),
            Action("Списать расход ресурса", Permission.CONSUME_RESOURCE, self.consume),
            Action("Заявки на пополнение", Permission.VIEW, self.show_requests),
            Action("Утвердить / отклонить заявку", Permission.APPROVE_REQUEST, self.decide_request),
            Action("Принять поставку по заявке", Permission.RECEIVE_SUPPLY, self.receive_request),
            Action("Дизель-генераторы", Permission.VIEW, self.show_generators),
            Action("Внести моточасы генератора", Permission.LOG_GENERATOR, self.log_hours),
            Action("Провести плановое ТО генератора", Permission.SERVICE_GENERATOR, self.service_generator),
            Action("Записать нештатную ситуацию", Permission.LOG_INCIDENT, self.log_incident),
            Action("Журнал нештатных ситуаций", Permission.VIEW, self.show_incidents),
            Action("Отчёты руководителя", Permission.VIEW_REPORTS, self.show_report),
        ]

    # ----------------------------------------------------------- главный цикл
    def run(self) -> None:
        self.view.message("Автоматизированная система полярной станции")
        if not self._login():
            return
        while True:
            available = [a for a in self._actions
                         if AccessPolicy.can(self.actor.role, a.permission)]
            idx = self.view.menu(
                f"Главное меню — {self.actor.username} ({self.actor.role.value})",
                [a.label for a in available], exit_label="Выйти из системы")
            if idx is None:
                self.view.message("До свидания!")
                return
            if idx == -1:
                self.view.error("Неверный пункт меню")
                continue
            try:
                available[idx].handler()
            except StationError as exc:
                self.view.error(str(exc))
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception as exc:  # непредвиденная ошибка не должна ронять программу
                self.view.error(f"Внутренняя ошибка: {exc.__class__.__name__}")

    def _login(self) -> bool:
        for _ in range(3):
            username = self.view.ask("Логин")
            password = self.view.ask_secret("Пароль")
            try:
                self.actor = self.auth.login(username, password)
                return True
            except AccessDeniedError as exc:
                self.view.error(str(exc))
        self.view.error("Превышено число попыток входа")
        return False

    # ------------------------------------------------------------- сотрудники
    def show_staff(self):
        shifts = {s.id: s for s in self.staff.list_shifts(self.actor)}
        self.view.table("Смены", ["ID", "Название", "Начало", "Окончание"],
                        [(s.id, s.name, s.start_date, s.end_date) for s in shifts.values()])
        self.view.table("Сотрудники",
                        ["ID", "ФИО", "Специальность", "Квал.", "Прибыл", "Здоровье", "Смена"],
                        [(e.id, e.full_name, e.specialty.value, e.qualification,
                          e.arrival_date, e.health.value, shifts[e.shift_id].name)
                         for e in self.staff.list_employees(self.actor)])

    def create_shift(self):
        name = self.view.ask("Название смены")
        start = self.view.ask("Дата начала (ГГГГ-ММ-ДД)")
        end = self.view.ask("Дата окончания (ГГГГ-ММ-ДД)")
        shift = self.staff.create_shift(self.actor, name, start, end)
        self.view.success(f"Смена «{shift.name}» создана (ID {shift.id})")

    def register_employee(self):
        self.view.table("Смены", ["ID", "Название", "Начало", "Окончание"],
                        [(s.id, s.name, s.start_date, s.end_date)
                         for s in self.staff.list_shifts(self.actor)])
        shift_id = self.view.ask("ID смены")
        name = self.view.ask("ФИО")
        specialty = self.view.pick("Специальность", [(s.value, s.value) for s in Specialty])
        qualification = self.view.ask("Уровень квалификации (1–5)")
        arrival = self.view.ask("Дата прибытия", datetime.now().strftime("%Y-%m-%d"))
        health = self.view.pick("Состояние здоровья", [(h.value, h.value) for h in Health])
        e = self.staff.register_employee(self.actor, name, specialty, qualification,
                                         arrival, health, shift_id)
        self.view.success(f"{e.full_name} зачислен(а) в смену (ID {e.id})")

    # ------------------------------------------------------ приборы/измерения
    def show_instruments(self):
        today = datetime.now().date()
        self.view.table("Приборы", ["ID", "Название", "Измеряет", "Калибровка до", "Статус"],
                        [(i.id, i.name, MEASUREMENT_KINDS[i.kind_code].title, i.due_date,
                          "ок" if i.is_calibrated(today) else "ПРОСРОЧЕНА — блокирован")
                         for i in self.instruments.list(self.actor)])

    def calibrate(self):
        self.show_instruments()
        i = self.instruments.calibrate(self.actor, self.view.ask("ID прибора"),
                                       self.view.ask("Дата калибровки", datetime.now().strftime("%Y-%m-%d")))
        self.view.success(f"«{i.name}» откалиброван, действует до {i.due_date}")

    def record_measurement(self):
        kind = self.view.pick("Вид измерения",
                              [(c, f"{k.title}, {k.unit}") for c, k in MEASUREMENT_KINDS.items()])
        value = self.view.ask("Значение").replace(",", ".")
        self.show_instruments()
        instrument_id = self.view.ask("ID прибора")
        operator_id = (str(self.actor.employee_id) if self.actor.employee_id
                       else self.view.ask("ID оператора (сотрудника)"))
        when = self.view.ask("Время измерения (ГГГГ-ММ-ДД ЧЧ:ММ), Enter — сейчас") or None
        mid = self.measurements.record(self.actor, kind, value, instrument_id,
                                       operator_id, when)
        self.view.success(f"Измерение сохранено (ID {mid})")

    def show_measurements(self):
        self.view.table("Последние измерения",
                        ["ID", "Время", "Вид", "Значение", "Прибор", "Оператор"],
                        [(r["id"], r["measured_at"], MEASUREMENT_KINDS[r["kind_code"]].title,
                          f"{r['value']:g} {MEASUREMENT_KINDS[r['kind_code']].unit}",
                          r["instrument"], r["operator"])
                         for r in self.measurements.recent(self.actor)])

    # ------------------------------------------------------------------ склад
    def show_resources(self):
        self.view.table("Склад", ["ID", "Ресурс", "Остаток", "Норма", "Состояние"],
                        [(r.id, r.name, f"{r.quantity:g} {r.unit}", f"{r.min_norm:g}",
                          "НИЖЕ НОРМЫ" if r.below_norm else "норма")
                         for r in self.supply.list_resources(self.actor)])

    def consume(self):
        self.show_resources()
        result = self.supply.consume(self.actor, self.view.ask("ID ресурса"),
                                     self.view.ask("Расход").replace(",", "."))
        r = result.resource
        self.view.success(f"Списано. Остаток «{r.name}»: {r.quantity:g} {r.unit}")
        if result.auto_request:
            self.view.warning(f"Остаток ниже нормы — автоматически создана заявка "
                              f"№{result.auto_request.id} на {result.auto_request.quantity:g} {r.unit}")

    def show_requests(self):
        names = {r.id: r for r in self.supply.list_resources(self.actor)}
        self.view.table("Заявки на пополнение",
                        ["№", "Ресурс", "Количество", "Статус", "Создана", "Решение"],
                        [(q.id, names[q.resource_id].name,
                          f"{q.quantity:g} {names[q.resource_id].unit}", q.status.value,
                          q.created_at.strftime("%Y-%m-%d %H:%M"),
                          q.decided_at.strftime("%Y-%m-%d %H:%M") if q.decided_at else "—")
                         for q in self.supply.list_requests(self.actor)])

    def decide_request(self):
        self.show_requests()
        request_id = self.view.ask("№ заявки")
        choice = self.view.pick("Решение", [("y", "Утвердить"), ("n", "Отклонить")])
        if choice not in ("y", "n"):
            self.view.error("Нужно выбрать 1 или 2")
            return
        q = self.supply.decide(self.actor, request_id, choice == "y")
        self.view.success(f"Заявка №{q.id}: {q.status.value}")

    def receive_request(self):
        self.show_requests()
        q = self.supply.receive(self.actor, self.view.ask("№ утверждённой заявки"))
        self.view.success(f"Заявка №{q.id} исполнена, остаток пополнен")

    # ------------------------------------------------------------- генераторы
    def show_generators(self):
        self.view.table("Дизель-генераторы",
                        ["ID", "Название", "Моточасы", "До ТО, ч", "Состояние"],
                        [(g.id, g.name, f"{g.motohours:g}", f"{g.hours_to_service:g}",
                          "ТРЕБУЕТСЯ ТО" if g.needs_service else "ок")
                         for g in self.generators.list(self.actor)])

    def log_hours(self):
        self.show_generators()
        g = self.generators.log_hours(self.actor, self.view.ask("ID генератора"),
                                      self.view.ask("Моточасы за запись (0–24]").replace(",", "."))
        self.view.success(f"{g.name}: наработка {g.motohours:g} м/ч")
        if g.needs_service:
            self.view.warning(f"{g.name}: плановое ТО (каждые 250 м/ч) просрочено на "
                              f"{-g.hours_to_service:g} м/ч!")

    def service_generator(self):
        self.show_generators()
        g = self.generators.service(self.actor, self.view.ask("ID генератора"))
        self.view.success(f"ТО {g.name} выполнено на {g.motohours:g} м/ч")

    # ----------------------------------------------------- нештатные ситуации
    def log_incident(self):
        kind = self.view.pick("Тип события", [(k.value, k.value) for k in IncidentKind])
        when = self.view.ask("Время события (ГГГГ-ММ-ДД ЧЧ:ММ)",
                             datetime.now().strftime("%Y-%m-%d %H:%M"))
        description = self.view.ask("Характер события")
        measures = self.view.ask("Принятые меры")
        i = self.incidents.log(self.actor, kind, when, description, measures)
        self.view.success(f"Запись №{i.id} добавлена в журнал")

    def show_incidents(self):
        self.view.table("Журнал нештатных ситуаций",
                        ["№", "Время", "Тип", "Характер", "Принятые меры"],
                        [(i.id, i.occurred_at.strftime("%Y-%m-%d %H:%M"), i.kind.value,
                          i.description, i.measures_taken)
                         for i in self.incidents.list(self.actor)])

    # ------------------------------------------------------------------ отчёт
    def show_report(self):
        start = self.view.ask("Начало периода (ГГГГ-ММ-ДД), Enter — без ограничения") or None
        end = self.view.ask("Конец периода (ГГГГ-ММ-ДД), Enter — без ограничения") or None
        self.view.report(self.reports.build(self.actor, start, end))
