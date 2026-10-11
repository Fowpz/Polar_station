import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.database import Database
from model.entities import Generator, Health, Instrument, Shift
from model.errors import (AccessDeniedError, BusinessRuleError, NotFoundError,
                          ValidationError)
from model.seed import seed_demo
from model.services import (AuthService, GeneratorService, IncidentService,
                            InstrumentService, MeasurementService, ReportService,
                            StaffService, SupplyService)

NOW = datetime(2026, 10, 6, 12, 0)


def clock():
    return NOW


class Base(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        seed_demo(self.db, NOW)
        auth = AuthService(self.db, clock)
        self.boss = auth.login("boss", "boss123")
        self.observer = auth.login("observer", "observer123")
        self.engineer = auth.login("engineer", "engineer123")
        self.staff = StaffService(self.db, clock)
        self.instr = InstrumentService(self.db, clock)
        self.meas = MeasurementService(self.db, clock)
        self.supply = SupplyService(self.db, clock)
        self.gens = GeneratorService(self.db, clock)
        self.inc = IncidentService(self.db, clock)
        self.rep = ReportService(self.db, clock)

    def tearDown(self):
        self.db.close()


class TestAuth(Base):
    def test_wrong_password(self):
        with self.assertRaises(AccessDeniedError):
            AuthService(self.db).login("boss", "wrong")

    def test_sql_injection_in_login(self):
        with self.assertRaises(AccessDeniedError):
            AuthService(self.db).login("' OR '1'='1' --", "x")

    def test_passwords_not_stored_in_plain_text(self):
        rows = self.db.conn.execute("SELECT password_hash FROM users").fetchall()
        self.assertTrue(all("boss123" not in r[0] and "$" in r[0] for r in rows))


class TestAccessControlInModel(Base):
    """Права проверяются в Model — обход меню ничего не даёт."""

    def test_observer_cannot_create_shift(self):
        with self.assertRaises(AccessDeniedError):
            self.staff.create_shift(self.observer, "X", "2026-11-01", "2027-01-10")

    def test_observer_cannot_see_report(self):
        with self.assertRaises(AccessDeniedError):
            self.rep.build(self.observer)

    def test_engineer_cannot_approve_request(self):
        self.supply.consume(self.engineer, 1, 3000)
        with self.assertRaises(AccessDeniedError):
            self.supply.decide(self.engineer, 1, True)

    def test_observer_cannot_record_for_someone_else(self):
        with self.assertRaises(AccessDeniedError):
            self.meas.record(self.observer, "air_temp", -20, 1, 1)

    def test_no_actor_denied(self):
        with self.assertRaises(AccessDeniedError):
            self.staff.list_shifts(None)


class TestEmployees(Base):
    def test_register_ok(self):
        e = self.staff.register_employee(self.boss, "Новиков И.И.", "радист", 3,
                                         "2026-10-01", "годен", 1)
        self.assertIsNotNone(e.id)

    def test_unfit_rejected(self):
        with self.assertRaises(BusinessRuleError):
            self.staff.register_employee(self.boss, "Новиков И.И.", "радист", 3,
                                         "2026-10-01", "не годен", 1)

    def test_bad_qualification(self):
        for bad in (0, 6, "abc", 2.5):
            with self.assertRaises(ValidationError):
                self.staff.register_employee(self.boss, "Новиков И.И.", "радист", bad,
                                             "2026-10-01", "годен", 1)

    def test_empty_name_and_unknown_specialty(self):
        with self.assertRaises(ValidationError):
            self.staff.register_employee(self.boss, "  ", "радист", 3, "2026-10-01", "годен", 1)
        with self.assertRaises(ValidationError):
            self.staff.register_employee(self.boss, "А", "повар", 3, "2026-10-01", "годен", 1)

    def test_shift_duration_validated(self):
        with self.assertRaises(ValidationError):
            self.staff.create_shift(self.boss, "Короткая", "2026-11-01", "2026-11-10")

    def test_unknown_shift(self):
        with self.assertRaises(NotFoundError):
            self.staff.register_employee(self.boss, "А", "радист", 3, "2026-10-01", "годен", 99)


class TestMeasurements(Base):
    def test_record_ok(self):
        # наблюдатель = Петрова (id 2), термометр воздуха (id 1)
        mid = self.meas.record(self.observer, "air_temp", "-23.5", 1, 2)
        self.assertEqual(self.meas.recent(self.observer)[0]["id"], mid)

    def test_overdue_calibration_blocks(self):
        # солемер (id 6) просрочен
        with self.assertRaises(BusinessRuleError) as ctx:
            self.meas.record(self.boss, "salinity", 33, 6, 2)
        self.assertIn("заблокированы", str(ctx.exception))

    def test_recalibration_unblocks(self):
        self.instr.calibrate(self.engineer, 6)
        self.meas.record(self.boss, "salinity", 33, 6, 2)

    def test_value_ranges(self):
        for kind, instr, bad in [("air_temp", 1, -120), ("humidity", 2, 101),
                                 ("wind_speed", 3, -1), ("wind_dir", 4, 361),
                                 ("snow_depth", 5, -5), ("water_temp", 7, -10),
                                 ("ice", 8, 11), ("ice", 8, 3.5), ("air_temp", 1, "nan")]:
            with self.assertRaises(ValidationError, msg=f"{kind}={bad}"):
                self.meas.record(self.boss, kind, bad, instr, 2)

    def test_wrong_instrument_for_kind(self):
        with self.assertRaises(BusinessRuleError):
            self.meas.record(self.boss, "humidity", 50, 1, 2)

    def test_future_time_rejected(self):
        with self.assertRaises(ValidationError):
            self.meas.record(self.boss, "air_temp", -5, 1, 2, "2026-10-07 12:00")

    def test_operator_outside_shift(self):
        with self.assertRaises(BusinessRuleError):
            self.meas.record(self.boss, "air_temp", -5, 1, 2, "2026-01-01 12:00")


class TestSupply(Base):
    def test_consume_below_norm_creates_single_request(self):
        r = self.supply.consume(self.engineer, 1, 3000)   # 12000 -> 9000 < 10000
        self.assertIsNotNone(r.auto_request)
        self.assertEqual(r.auto_request.quantity, 11000)   # до двойной нормы
        r2 = self.supply.consume(self.engineer, 1, 100)
        self.assertIsNone(r2.auto_request)                 # дубликат не создаётся

    def test_no_request_above_norm(self):
        self.assertIsNone(self.supply.consume(self.engineer, 1, 500).auto_request)

    def test_consume_more_than_stock(self):
        with self.assertRaises(BusinessRuleError):
            self.supply.consume(self.engineer, 3, 1000)

    def test_negative_or_zero_consumption(self):
        for bad in (0, -5, "x"):
            with self.assertRaises(ValidationError):
                self.supply.consume(self.engineer, 1, bad)

    def test_full_request_lifecycle(self):
        self.supply.consume(self.engineer, 1, 3000)
        with self.assertRaises(BusinessRuleError):          # нельзя принять неутверждённую
            self.supply.receive(self.engineer, 1)
        self.supply.decide(self.boss, 1, True)
        with self.assertRaises(BusinessRuleError):          # нельзя решить дважды
            self.supply.decide(self.boss, 1, False)
        self.supply.receive(self.engineer, 1)
        self.assertEqual(self.supply.list_resources(self.boss)[0].quantity, 20000)

    def test_sql_injection_in_id(self):
        with self.assertRaises(ValidationError):
            self.supply.consume(self.engineer, "1; DROP TABLE resources", 1)


class TestGenerators(Base):
    def test_service_due_at_250(self):
        g1, g2 = self.gens.list(self.boss)
        self.assertFalse(g1.needs_service)   # 180 м/ч
        self.assertTrue(g2.needs_service)    # 260 м/ч

    def test_log_hours_triggers_due(self):
        g = self.gens.log_hours(self.engineer, 1, 24)
        self.assertEqual(g.motohours, 1204)
        for _ in range(3):
            g = self.gens.log_hours(self.engineer, 1, 24)
        self.assertTrue(g.needs_service)     # 252 м/ч

    def test_service_resets_counter(self):
        g = self.gens.service(self.engineer, 2)
        self.assertFalse(g.needs_service)
        self.assertEqual(g.hours_to_service, 250)

    def test_invalid_hours(self):
        for bad in (0, -1, 25, "abc"):
            with self.assertRaises(ValidationError):
                self.gens.log_hours(self.engineer, 1, bad)

    def test_entity_invariant(self):
        with self.assertRaises(ValidationError):
            Generator("ДГ", 100, 200)


class TestIncidents(Base):
    def test_log_ok_and_requires_measures(self):
        self.inc.log(self.observer, "пурга", "2026-10-05 08:00", "Видимость < 50 м", "Работы остановлены")
        self.assertEqual(len(self.inc.list(self.boss)), 1)
        with self.assertRaises(ValidationError):
            self.inc.log(self.observer, "шторм", "2026-10-05 08:00", "Сильный ветер", "")

    def test_unknown_kind_and_future(self):
        with self.assertRaises(ValidationError):
            self.inc.log(self.observer, "землетрясение", "2026-10-05 08:00", "а", "б")
        with self.assertRaises(ValidationError):
            self.inc.log(self.observer, "шторм", "2027-01-01 08:00", "а", "б")


class TestReport(Base):
    def test_report_content(self):
        self.meas.record(self.observer, "air_temp", -20, 1, 2)
        self.meas.record(self.observer, "air_temp", -21, 1, 2)
        self.supply.consume(self.engineer, 1, 500)
        self.inc.log(self.observer, "шторм", "2026-10-05 08:00", "а", "б")
        data = self.rep.build(self.boss)
        self.assertEqual(dict(data["observations"])["Температура воздуха"], 2)
        self.assertEqual(data["consumption"][0][2], 500)
        self.assertEqual(data["incidents_total"], 1)
        rows = data["staffing"][0]["rows"]
        self.assertTrue(all(r[3] == "норма" for r in rows))

    def test_period_filter_and_validation(self):
        self.meas.record(self.observer, "air_temp", -20, 1, 2)
        data = self.rep.build(self.boss, "2020-01-01", "2020-12-31")
        self.assertEqual(sum(n for _, n in data["observations"]), 0)
        with self.assertRaises(ValidationError):
            self.rep.build(self.boss, "2026-12-01", "2026-01-01")


if __name__ == "__main__":
    unittest.main(verbosity=2)
