"""Точка входа: сборка слоёв MVC. По умолчанию — окно tkinter, --console — консоль."""
import argparse

from model.database import Database
from model.seed import seed_demo
from model.services import (AuthService, GeneratorService, IncidentService,
                            InstrumentService, MeasurementService, ReportService,
                            StaffService, SupplyService)


def build_services(db: Database) -> tuple:
    return (AuthService(db), StaffService(db), InstrumentService(db),
            MeasurementService(db), SupplyService(db), GeneratorService(db),
            IncidentService(db), ReportService(db))


def build_controller(db: Database, view, gui: bool = True):
    if gui:
        from controller.gui_controller import GuiController as Ctl
    else:
        from controller.controller import Controller as Ctl
    return Ctl(view, *build_services(db))


def main() -> None:
    parser = argparse.ArgumentParser(description="Полярная станция — учётная система")
    parser.add_argument("--db", default="polar_station.db", help="путь к файлу SQLite")
    parser.add_argument("--console", action="store_true",
                        help="консольный интерфейс вместо графического")
    args = parser.parse_args()
    db = Database(args.db)
    try:
        seed_demo(db)
        if args.console:
            from view.console_view import ConsoleView
            build_controller(db, ConsoleView(), gui=False).run()
        else:
            from view.gui_view import GuiView
            build_controller(db, GuiView(), gui=True).run()
    except (KeyboardInterrupt, EOFError):
        print("\nЗавершение работы.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
