"""View: только ввод/вывод. Никакой бизнес-логики и обращения к БД."""
import getpass
from typing import Callable, List, Optional, Sequence, Tuple


class ConsoleView:
    def __init__(self, input_fn: Callable = input, print_fn: Callable = print,
                 secret_fn: Callable = getpass.getpass):
        self._input, self._print, self._secret = input_fn, print_fn, secret_fn

    # --- ввод
    def ask(self, prompt: str, default: Optional[str] = None) -> str:
        suffix = f" [{default}]" if default else ""
        raw = self._input(f"{prompt}{suffix}: ").strip()
        return raw if raw else (default or "")

    def ask_secret(self, prompt: str) -> str:
        return self._secret(f"{prompt}: ")

    def menu(self, title: str, labels: Sequence[str], exit_label: str = "Выход") -> Optional[int]:
        """Возвращает индекс выбранного пункта или None для выхода."""
        self._print(f"\n=== {title} ===")
        for i, label in enumerate(labels, 1):
            self._print(f"  {i}. {label}")
        self._print(f"  0. {exit_label}")
        raw = self._input("Выбор: ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(labels):
            return int(raw) - 1
        return -1  # неверный ввод

    def pick(self, title: str, options: List[Tuple[str, str]]) -> str:
        """Выбор из списка (ключ, подпись) по номеру; возвращает ключ."""
        self._print(f"{title}:")
        for i, (_, label) in enumerate(options, 1):
            self._print(f"  {i}. {label}")
        raw = self._input("Номер: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        return raw  # Model сама отклонит некорректное значение

    # --- вывод
    def message(self, text: str) -> None:
        self._print(text)

    def success(self, text: str) -> None:
        self._print(f"[OK] {text}")

    def warning(self, text: str) -> None:
        self._print(f"[!] {text}")

    def error(self, text: str) -> None:
        self._print(f"[ОШИБКА] {text}")

    def table(self, title: str, headers: Sequence[str], rows: Sequence[Sequence]) -> None:
        self._print(f"\n--- {title} ---")
        if not rows:
            self._print("(нет данных)")
            return
        text = [[str(c) for c in r] for r in rows]
        widths = [max(len(h), *(len(r[i]) for r in text)) for i, h in enumerate(headers)]
        line = "  ".join(h.ljust(w) for h, w in zip(headers, widths))
        self._print(line)
        self._print("-" * len(line))
        for r in text:
            self._print("  ".join(c.ljust(w) for c, w in zip(r, widths)))

    def report(self, data: dict) -> None:
        start, end = data["period"]
        self._print(f"\n##### ОТЧЁТ РУКОВОДИТЕЛЯ (период: {start or 'начало'} — {end or 'сейчас'}) #####")
        self.table("Объём наблюдений по типам", ["Тип", "Количество"], data["observations"])
        self.table("Расход топлива и материалов", ["Ресурс", "Ед.", "Израсходовано"],
                   [(n, u, f"{t:g}") for n, u, t in data["consumption"]])
        self._print(f"\nНештатных ситуаций всего: {data['incidents_total']}")
        for kind, n in data["incidents_by_kind"]:
            self._print(f"  - {kind}: {n}")
        for block in data["staffing"]:
            self.table(f"Укомплектованность — {block['shift']}",
                       ["Специальность", "Есть", "Нужно", "Статус"], block["rows"])
