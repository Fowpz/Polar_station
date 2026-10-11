"""Controller для графического (tkinter) интерфейса.

Описывает вкладки и формы, вызывает сервисы Model и показывает результат во View.
Ошибки Model не подавляются — превращаются в понятное окно с сообщением.
"""
from datetime import datetime
from typing import Callable, Dict, List, Optional

from model.entities import Health, IncidentKind, MEASUREMENT_KINDS, Specialty
from model.errors import AccessDeniedError, StationError
from model.security import AccessPolicy, Actor, Permission
from view.gui_view import Button, Field, Tab, Table

LOGIN_HINT = ("Демо-учётки:\nboss / boss123   ·   observer / observer123   ·   "
              "engineer / engineer123")
MAX_LOGIN_ATTEMPTS = 3
FMT_DATE, FMT_DT = "%Y-%m-%d", "%Y-%m-%d %H:%M"


def _today() -> str:
    return datetime.now().strftime(FMT_DATE)


def _now() -> str:
    return datetime.now().strftime(FMT_DT)


class GuiController:
    def __init__(self, view, auth, staff, instruments, measurements, supply,
                 generators, incidents, reports):
        self.view = view
        self.auth, self.staff, self.instruments = auth, staff, instruments
        self.measurements, self.supply, self.generators = measurements, supply, generators
        self.incidents, self.reports = incidents, reports
        self.actor: Optional[Actor] = None
        self._attempts = 0
        self._report_period = (None, None)
        self._refreshers: List[Callable[[], None]] = []

    # ---------------------------------------------------------------- запуск
    def run(self) -> None:
        self._show_login()
        self.view.run()

    # ----------------------------------------------------------------- вход
    def _show_login(self) -> None:
        self.actor = None
        self._attempts = 0
        self.view.show_login(self._login, LOGIN_HINT)

    def _login(self, username: str, password: str) -> None:
        try:
            self.actor = self.auth.login(username, password)
        except AccessDeniedError as exc:
            self._attempts += 1
            self.view.error(str(exc))
            if self._attempts >= MAX_LOGIN_ATTEMPTS:
                self.view.error("Превышено число попыток входа")
                self.view.close()
            return
        self._show_main()

    def _can(self, permission: Permission) -> bool:
        return AccessPolicy.can(self.actor.role, permission)

    # --------------------------------------------------------- главное окно
    def _show_main(self) -> None:
        self._refreshers = []
        tabs: List[Tab] = []

        def tab(key, title, tables, buttons, refresh, text_report=False):
            btns = [Button(label, self._guard(handler))
                    for label, perm, handler in buttons if self._can(perm)]
            tabs.append(Tab(key, title, tables, btns, text_report))
            self._refreshers.append(self._guard(refresh, quiet=True))

        tab("staff", "Смены и сотрудники",
            [Table("Смены", ["ID", "Название", "Начало", "Окончание"], 4),
             Table("Сотрудники", ["ID", "ФИО", "Специальность", "Квал.", "Прибыл",
                                  "Здоровье", "Смена"], 10)],
            [("Создать смену", Permission.MANAGE_STAFF, self.create_shift),
             ("Зачислить сотрудника", Permission.MANAGE_STAFF, self.register_employee)],
            self.refresh_staff)
        tab("meas", "Измерения",
            [Table("Последние измерения", ["ID", "Время", "Вид", "Значение", "Прибор",
                                           "Оператор"], 16)],
            [("Внести измерение", Permission.RECORD_MEASUREMENT, self.record_measurement)],
            self.refresh_measurements)
        tab("instr", "Приборы",
            [Table("Приборы и калибровка", ["ID", "Название", "Измеряет", "Калибровка до",
                                            "Статус"], 16)],
            [("Провести калибровку", Permission.CALIBRATE, self.calibrate)],
            self.refresh_instruments)
        tab("stock", "Склад и заявки",
            [Table("Склад", ["ID", "Ресурс", "Остаток", "Норма", "Состояние"], 5),
             Table("Заявки на пополнение", ["№", "Ресурс", "Количество", "Статус",
                                            "Создана", "Решение"], 8)],
            [("Списать расход", Permission.CONSUME_RESOURCE, self.consume),
             ("Утвердить заявку", Permission.APPROVE_REQUEST, lambda: self.decide(True)),
             ("Отклонить заявку", Permission.APPROVE_REQUEST, lambda: self.decide(False)),
             ("Принять поставку", Permission.RECEIVE_SUPPLY, self.receive)],
            self.refresh_stock)
        tab("gen", "Генераторы",
            [Table("Дизель-генераторы", ["ID", "Название", "Моточасы", "До ТО, ч",
                                         "Состояние"], 10)],
            [("Внести моточасы", Permission.LOG_GENERATOR, self.log_hours),
             ("Плановое ТО", Permission.SERVICE_GENERATOR, self.service_generator)],
            self.refresh_generators)
        tab("inc", "Нештатные ситуации",
            [Table("Журнал нештатных ситуаций", ["№", "Время", "Тип", "Характер",
                                                 "Принятые меры"], 16)],
            [("Записать ситуацию", Permission.LOG_INCIDENT, self.log_incident)],
            self.refresh_incidents)
        if self._can(Permission.VIEW_REPORTS):
            tab("report", "Отчёты", [],
                [("Сформировать отчёт…", Permission.VIEW_REPORTS, self.choose_period),
                 ("Обновить", Permission.VIEW_REPORTS, self.refresh_report)],
                self.refresh_report, text_report=True)

        self.view.show_main(f"{self.actor.username} ({self.actor.role.value})", tabs,
                            self._show_login)
        self.refresh_all()

    def refresh_all(self) -> None:
        for refresh in self._refreshers:
            refresh()

    def _guard(self, fn: Callable, quiet: bool = False) -> Callable[[], None]:
        """Ошибки Model -> окно с сообщением; действие обновляет все вкладки."""
        def wrapper():
            try:
                fn()
            except StationError as exc:
                self.view.error(str(exc))
            except Exception as exc:  # непредвиденная ошибка не должна ронять программу
                self.view.error(f"Внутренняя ошибка: {exc.__class__.__name__}: {exc}")
            if not quiet:
                self.refresh_all()
        return wrapper

    # ---------------------------------------------------------- обновление
    def refresh_staff(self):
        shifts = self.staff.list_shifts(self.actor)
        names = {s.id: s.name for s in shifts}
        self.view.set_table("staff", 0, [(s.id, s.name, s.start_date, s.end_date)
                                         for s in shifts])
        self.view.set_table("staff", 1, [
            (e.id, e.full_name, e.specialty.value, e.qualification, e.arrival_date,
             e.health.value, names.get(e.shift_id, "?"))
            for e in self.staff.list_employees(self.actor)])

    def refresh_measurements(self):
        rows = self.measurements.recent(self.actor, 50)
        self.view.set_table("meas", 0, [
            (r["id"], r["measured_at"], MEASUREMENT_KINDS[r["kind_code"]].title,
             f"{r['value']:g} {MEASUREMENT_KINDS[r['kind_code']].unit}",
             r["instrument"], r["operator"]) for r in rows])

    def refresh_instruments(self):
        today = datetime.now().date()
        items = self.instruments.list(self.actor)
        self.view.set_table("instr", 0, [
            (i.id, i.name, MEASUREMENT_KINDS[i.kind_code].title, i.due_date,
             "ок" if i.is_calibrated(today) else "ПРОСРОЧЕНА — блокирован")
            for i in items], [not i.is_calibrated(today) for i in items])

    def refresh_stock(self):
        resources = self.supply.list_resources(self.actor)
        by_id = {r.id: r for r in resources}
        self.view.set_table("stock", 0, [
            (r.id, r.name, f"{r.quantity:g} {r.unit}", f"{r.min_norm:g}",
             "НИЖЕ НОРМЫ" if r.below_norm else "норма") for r in resources],
            [r.below_norm for r in resources])
        self.view.set_table("stock", 1, [
            (q.id, by_id[q.resource_id].name,
             f"{q.quantity:g} {by_id[q.resource_id].unit}", q.status.value,
             q.created_at.strftime(FMT_DT),
             q.decided_at.strftime(FMT_DT) if q.decided_at else "—")
            for q in self.supply.list_requests(self.actor)])

    def refresh_generators(self):
        gens = self.generators.list(self.actor)
        self.view.set_table("gen", 0, [
            (g.id, g.name, f"{g.motohours:g}", f"{g.hours_to_service:g}",
             "ТРЕБУЕТСЯ ТО" if g.needs_service else "ок") for g in gens],
            [g.needs_service for g in gens])

    def refresh_incidents(self):
        self.view.set_table("inc", 0, [
            (i.id, i.occurred_at.strftime(FMT_DT), i.kind.value, i.description,
             i.measures_taken) for i in self.incidents.list(self.actor)])

    def refresh_report(self):
        start, end = self._report_period
        data = self.reports.build(self.actor, start, end)
        p_start, p_end = data["period"]
        lines = [(f"ОТЧЁТ РУКОВОДИТЕЛЯ  (период: {p_start or 'начало'} — {p_end or 'сейчас'})", "h"),
                 ("", "")]

        def table(title, headers, rows, warn_col=None):
            lines.append((title, "h"))
            if not rows:
                lines.append(("  (нет данных)", ""))
            else:
                text = [[str(c) for c in r] for r in rows]
                w = [max(len(h), *(len(r[i]) for r in text)) for i, h in enumerate(headers)]
                lines.append(("  " + "  ".join(h.ljust(x) for h, x in zip(headers, w)), ""))
                lines.append(("  " + "-" * (sum(w) + 2 * (len(w) - 1)), ""))
                for r in text:
                    bad = warn_col is not None and r[warn_col] == "НЕДОКОМПЛЕКТ"
                    lines.append(("  " + "  ".join(c.ljust(x) for c, x in zip(r, w)),
                                  "warn" if bad else ""))
            lines.append(("", ""))

        table("Объём наблюдений по типам", ["Тип", "Количество"], data["observations"])
        table("Расход топлива и материалов", ["Ресурс", "Ед.", "Израсходовано"],
              [(n, u, f"{t:g}") for n, u, t in data["consumption"]])
        table(f"Нештатные ситуации (всего: {data['incidents_total']})",
              ["Тип", "Количество"], data["incidents_by_kind"])
        for block in data["staffing"]:
            table(f"Укомплектованность — {block['shift']}",
                  ["Специальность", "Есть", "Нужно", "Статус"], block["rows"], warn_col=3)
        self.view.set_text("report", lines)

    # ------------------------------------------------------------ сотрудники
    def create_shift(self):
        v = self.view.form("Создать смену", [
            Field("name", "Название смены"),
            Field("start", "Дата начала (ГГГГ-ММ-ДД)", default=_today()),
            Field("end", "Дата окончания (ГГГГ-ММ-ДД)")],
            hint="Длительность смены — от 56 до 95 дней.")
        if v is None:
            return
        shift = self.staff.create_shift(self.actor, v["name"], v["start"], v["end"])
        self.view.success(f"Смена «{shift.name}» создана (ID {shift.id})")

    def register_employee(self):
        shifts = self.staff.list_shifts(self.actor)
        selected = self.view.selected("staff", 0)
        v = self.view.form("Зачислить сотрудника в смену", [
            Field("shift", "Смена", "choice", [(str(s.id), f"{s.name} (ID {s.id})")
                                                for s in shifts],
                  selected or (str(shifts[-1].id) if shifts else "")),
            Field("name", "ФИО"),
            Field("specialty", "Специальность", "choice",
                  [(s.value, s.value) for s in Specialty]),
            Field("qual", "Квалификация (1–5)", default="3"),
            Field("arrival", "Дата прибытия", default=_today()),
            Field("health", "Здоровье", "choice", [(h.value, h.value) for h in Health])])
        if v is None:
            return
        e = self.staff.register_employee(self.actor, v["name"], v["specialty"], v["qual"],
                                         v["arrival"], v["health"], v["shift"])
        self.view.success(f"{e.full_name} зачислен(а) в смену (ID {e.id})")

    # ------------------------------------------------------ приборы/измерения
    def calibrate(self):
        items = self.instruments.list(self.actor)
        v = self.view.form("Калибровка прибора", [
            Field("id", "Прибор", "choice", [(str(i.id), i.name) for i in items],
                  self.view.selected("instr") or ""),
            Field("date", "Дата калибровки", default=_today())])
        if v is None:
            return
        i = self.instruments.calibrate(self.actor, v["id"], v["date"])
        self.view.success(f"«{i.name}» откалиброван, действует до {i.due_date}")

    def record_measurement(self):
        instruments = self.instruments.list(self.actor)
        fields = [
            Field("kind", "Вид измерения", "choice",
                  [(c, f"{k.title}, {k.unit}") for c, k in MEASUREMENT_KINDS.items()]),
            Field("value", "Значение"),
            Field("instrument", "Прибор", "choice",
                  [(str(i.id), f"{i.name} — {MEASUREMENT_KINDS[i.kind_code].title}")
                   for i in instruments])]
        if self.actor.employee_id:
            operator_id = str(self.actor.employee_id)
        else:
            fields.append(Field("operator", "Оператор", "choice",
                                [(str(e.id), e.full_name)
                                 for e in self.staff.list_employees(self.actor)]))
            operator_id = None
        fields.append(Field("when", "Время (ГГГГ-ММ-ДД ЧЧ:ММ)", default=_now()))
        v = self.view.form("Внести измерение", fields,
                           hint="Прибор с просроченной калибровкой заблокирован.")
        if v is None:
            return
        mid = self.measurements.record(self.actor, v["kind"], v["value"].replace(",", "."),
                                       v["instrument"], operator_id or v["operator"],
                                       v["when"] or None)
        self.view.success(f"Измерение сохранено (ID {mid})")

    # ----------------------------------------------------------------- склад
    def consume(self):
        resources = self.supply.list_resources(self.actor)
        v = self.view.form("Списать расход ресурса", [
            Field("id", "Ресурс", "choice",
                  [(str(r.id), f"{r.name} (остаток {r.quantity:g} {r.unit})")
                   for r in resources], self.view.selected("stock", 0) or ""),
            Field("amount", "Расход")])
        if v is None:
            return
        result = self.supply.consume(self.actor, v["id"], v["amount"].replace(",", "."))
        r = result.resource
        self.view.success(f"Списано. Остаток «{r.name}»: {r.quantity:g} {r.unit}")
        if result.auto_request:
            self.view.warning(f"Остаток «{r.name}» ниже нормы — автоматически создана "
                              f"заявка №{result.auto_request.id} на "
                              f"{result.auto_request.quantity:g} {r.unit}")

    def _selected_request(self, title: str) -> Optional[str]:
        request_id = self.view.selected("stock", 1)
        if request_id is None:
            self.view.message(f"{title}: выберите заявку в таблице «Заявки на пополнение».")
        return request_id

    def decide(self, approve: bool):
        request_id = self._selected_request("Решение по заявке")
        if request_id is None:
            return
        q = self.supply.decide(self.actor, request_id, approve)
        self.view.success(f"Заявка №{q.id}: {q.status.value}")

    def receive(self):
        request_id = self._selected_request("Приём поставки")
        if request_id is None:
            return
        q = self.supply.receive(self.actor, request_id)
        self.view.success(f"Заявка №{q.id} исполнена, остаток пополнен")

    # ------------------------------------------------------------ генераторы
    def _pick_generator(self, title: str, extra=()) -> Optional[Dict[str, str]]:
        gens = self.generators.list(self.actor)
        return self.view.form(title, [
            Field("id", "Генератор", "choice",
                  [(str(g.id), f"{g.name} ({g.motohours:g} м/ч)") for g in gens],
                  self.view.selected("gen") or ""), *extra])

    def log_hours(self):
        v = self._pick_generator("Внести моточасы", [Field("hours", "Моточасы за запись (0–24]")])
        if v is None:
            return
        g = self.generators.log_hours(self.actor, v["id"], v["hours"].replace(",", "."))
        self.view.success(f"{g.name}: наработка {g.motohours:g} м/ч")
        if g.needs_service:
            self.view.warning(f"{g.name}: плановое ТО (каждые 250 м/ч) просрочено на "
                              f"{-g.hours_to_service:g} м/ч!")

    def service_generator(self):
        v = self._pick_generator("Плановое ТО генератора")
        if v is None:
            return
        g = self.generators.service(self.actor, v["id"])
        self.view.success(f"ТО {g.name} выполнено на {g.motohours:g} м/ч")

    # ----------------------------------------------------- нештатные ситуации
    def log_incident(self):
        v = self.view.form("Нештатная ситуация", [
            Field("kind", "Тип события", "choice", [(k.value, k.value) for k in IncidentKind]),
            Field("when", "Время (ГГГГ-ММ-ДД ЧЧ:ММ)", default=_now()),
            Field("desc", "Характер события"),
            Field("measures", "Принятые меры")],
            hint="Принятые меры обязательны.")
        if v is None:
            return
        i = self.incidents.log(self.actor, v["kind"], v["when"], v["desc"], v["measures"])
        self.view.success(f"Запись №{i.id} добавлена в журнал")

    # ------------------------------------------------------------------ отчёт
    def choose_period(self):
        start, end = self._report_period
        v = self.view.form("Период отчёта", [
            Field("start", "Начало (ГГГГ-ММ-ДД)", default=start or ""),
            Field("end", "Конец (ГГГГ-ММ-ДД)", default=end or "")],
            hint="Пустое поле — без ограничения.")
        if v is None:
            return
        old, self._report_period = self._report_period, (v["start"] or None, v["end"] or None)
        try:
            self.refresh_report()
        except StationError:
            self._report_period = old   # неверный период не должен ломать вкладку
            raise
        self.view.success("Отчёт сформирован")
