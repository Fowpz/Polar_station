"""View (tkinter): только виджеты и ввод/вывод. Никакой бизнес-логики и обращения к БД.

View ничего не знает о Model: Controller описывает вкладки, таблицы, кнопки и формы
простыми структурами (Tab, Table, Button, Field), а View их рисует.
"""
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

APP_TITLE = "Полярная станция — учётная система"


class Table(NamedTuple):
    title: str
    headers: Sequence[str]
    height: int = 8


class Button(NamedTuple):
    label: str
    handler: Callable[[], None]


class Tab(NamedTuple):
    key: str
    title: str
    tables: Sequence[Table]
    buttons: Sequence[Button] = ()
    text_report: bool = False     # вкладка с текстовым отчётом вместо таблиц


class Field(NamedTuple):
    name: str
    label: str
    kind: str = "text"                                 # "text" | "choice"
    options: Sequence[Tuple[str, str]] = ()            # для choice: (значение, подпись)
    default: str = ""


class _FormDialog(tk.Toplevel):
    def __init__(self, parent, title: str, fields: Sequence[Field], hint: str = ""):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result: Optional[Dict[str, str]] = None
        self._vars: Dict[str, tk.StringVar] = {}
        self._choices: Dict[str, Dict[str, str]] = {}

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        row = 0
        if hint:
            ttk.Label(body, text=hint, foreground="#555", wraplength=380,
                      justify="left").grid(row=row, column=0, columnspan=2,
                                           sticky="w", pady=(0, 8))
            row += 1
        first = None
        for f in fields:
            ttk.Label(body, text=f.label).grid(row=row, column=0, sticky="w",
                                               padx=(0, 10), pady=4)
            var = tk.StringVar()
            if f.kind == "choice":
                labels = [lbl for _, lbl in f.options]
                self._choices[f.name] = {lbl: val for val, lbl in f.options}
                w = ttk.Combobox(body, textvariable=var, values=labels,
                                 state="readonly", width=42)
                chosen = next((lbl for val, lbl in f.options if val == f.default), None)
                if chosen is None and labels:
                    chosen = labels[0]
                var.set(chosen or "")
            else:
                var.set(f.default)
                w = ttk.Entry(body, textvariable=var, width=45)
            w.grid(row=row, column=1, sticky="ew", pady=4)
            self._vars[f.name] = var
            first = first or w
            row += 1

        btns = ttk.Frame(body)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="OK", command=self._ok, default="active").pack(side="right")
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 80, parent.winfo_rooty() + 80))
        if first:
            first.focus_set()
        self.grab_set()

    def _ok(self):
        self.result = {}
        for name, var in self._vars.items():
            raw = var.get().strip()
            self.result[name] = self._choices[name].get(raw, raw) if name in self._choices else raw
        self.destroy()


class GuiView:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1000x620")
        self.root.minsize(820, 480)
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))
        self._trees: Dict[Tuple[str, int], ttk.Treeview] = {}
        self._texts: Dict[str, tk.Text] = {}
        self._status = tk.StringVar()
        self._notebook: Optional[ttk.Notebook] = None
        self._main_frame: Optional[ttk.Frame] = None

    # ------------------------------------------------------------- жизненный цикл
    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.root.destroy()

    def clear(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self._trees.clear()
        self._texts.clear()
        self._notebook = None

    # ---------------------------------------------------------------- вход
    def show_login(self, on_submit: Callable[[str, str], None], hint: str = "") -> None:
        self.clear()
        self.root.title(APP_TITLE)
        outer = ttk.Frame(self.root)
        outer.place(relx=0.5, rely=0.45, anchor="center")
        ttk.Label(outer, text="Полярная станция", font=("TkDefaultFont", 20, "bold")
                  ).grid(row=0, column=0, columnspan=2, pady=(0, 2))
        ttk.Label(outer, text="Автоматизированная учётная система", foreground="#555"
                  ).grid(row=1, column=0, columnspan=2, pady=(0, 18))
        user, pwd = tk.StringVar(), tk.StringVar()
        ttk.Label(outer, text="Логин").grid(row=2, column=0, sticky="w", pady=4, padx=(0, 10))
        e_user = ttk.Entry(outer, textvariable=user, width=26)
        e_user.grid(row=2, column=1, pady=4)
        ttk.Label(outer, text="Пароль").grid(row=3, column=0, sticky="w", pady=4)
        e_pwd = ttk.Entry(outer, textvariable=pwd, show="•", width=26)
        e_pwd.grid(row=3, column=1, pady=4)
        submit = lambda *_: on_submit(user.get(), pwd.get())  # noqa: E731
        ttk.Button(outer, text="Войти", command=submit).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(14, 6))
        if hint:
            ttk.Label(outer, text=hint, foreground="#777", justify="center"
                      ).grid(row=5, column=0, columnspan=2, pady=(10, 0))
        self.root.bind("<Return>", submit)
        e_user.focus_set()

    # ------------------------------------------------------------- главное окно
    def show_main(self, title: str, tabs: Sequence[Tab], on_logout: Callable[[], None]) -> None:
        self.clear()
        self.root.unbind("<Return>")
        self.root.title(f"{APP_TITLE} — {title}")

        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        ttk.Label(top, text=title, font=("TkDefaultFont", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Выйти из системы", command=on_logout).pack(side="right")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10)
        self._notebook = nb
        for tab in tabs:
            self._build_tab(nb, tab)

        ttk.Label(self.root, textvariable=self._status, relief="sunken", anchor="w",
                  padding=(8, 3)).pack(fill="x", side="bottom", pady=(6, 0))
        self._status.set("Готово")

    def _build_tab(self, nb: ttk.Notebook, tab: Tab) -> None:
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text=tab.title)
        if tab.buttons:
            bar = ttk.Frame(frame)
            bar.pack(fill="x", pady=(0, 8))
            for b in tab.buttons:
                ttk.Button(bar, text=b.label, command=b.handler).pack(side="left", padx=(0, 6))
        if tab.text_report:
            box = ttk.Frame(frame)
            box.pack(fill="both", expand=True)
            text = tk.Text(box, wrap="none", font=("DejaVu Sans Mono", 10), state="disabled",
                           padx=8, pady=6)
            sy = ttk.Scrollbar(box, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=sy.set)
            sy.pack(side="right", fill="y")
            text.pack(side="left", fill="both", expand=True)
            text.tag_configure("h", font=("DejaVu Sans Mono", 11, "bold"))
            text.tag_configure("warn", foreground="#b3261e")
            self._texts[tab.key] = text
            return
        for i, table in enumerate(tab.tables):
            ttk.Label(frame, text=table.title, font=("TkDefaultFont", 10, "bold")
                      ).pack(anchor="w", pady=(4, 2))
            box = ttk.Frame(frame)
            box.pack(fill="both", expand=True)
            tree = ttk.Treeview(box, columns=list(range(len(table.headers))),
                                show="headings", height=table.height, selectmode="browse")
            for j, h in enumerate(table.headers):
                tree.heading(j, text=h)
                tree.column(j, width=110, minwidth=50, anchor="w")
            sy = ttk.Scrollbar(box, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sy.set)
            sy.pack(side="right", fill="y")
            tree.pack(side="left", fill="both", expand=True)
            tree.tag_configure("warn", background="#fde8e6", foreground="#8c1d18")
            tree.tag_configure("ok", foreground="#1b5e20")
            self._trees[(tab.key, i)] = tree

    # ------------------------------------------------------------------- данные
    def set_table(self, tab_key: str, index: int, rows: Sequence[Sequence],
                  warn_rows: Sequence[bool] = ()) -> None:
        tree = self._trees.get((tab_key, index))
        if tree is None:
            return
        tree.delete(*tree.get_children())
        data = [[str(c) for c in r] for r in rows]
        for n, r in enumerate(data):
            tag = ("warn",) if n < len(warn_rows) and warn_rows[n] else ()
            tree.insert("", "end", values=r, tags=tag)
        # авто-ширина колонок по содержимому
        cols = tree["columns"]
        for j, col in enumerate(cols):
            head = tree.heading(col, "text")
            longest = max([len(head)] + [len(r[j]) for r in data[:200]])
            tree.column(col, width=min(max(longest * 9 + 20, 70), 420))

    def selected(self, tab_key: str, index: int = 0) -> Optional[str]:
        """Значение первой колонки выбранной строки (обычно ID) или None."""
        tree = self._trees.get((tab_key, index))
        sel = tree.selection() if tree else ()
        return str(tree.item(sel[0], "values")[0]) if sel else None

    def set_text(self, tab_key: str, lines: Sequence[Tuple[str, str]]) -> None:
        """lines: (текст, стиль) где стиль '', 'h' или 'warn'."""
        text = self._texts.get(tab_key)
        if text is None:
            return
        text.configure(state="normal")
        text.delete("1.0", "end")
        for line, style in lines:
            text.insert("end", line + "\n", style or ())
        text.configure(state="disabled")

    # ---------------------------------------------------------------- диалоги
    def form(self, title: str, fields: Sequence[Field], hint: str = "") -> Optional[Dict[str, str]]:
        dlg = _FormDialog(self.root, title, fields, hint)
        self.root.wait_window(dlg)
        return dlg.result

    def confirm(self, text: str) -> bool:
        return messagebox.askyesno(APP_TITLE, text, parent=self.root)

    def message(self, text: str) -> None:
        messagebox.showinfo(APP_TITLE, text, parent=self.root)

    def success(self, text: str) -> None:
        self._status.set(text)

    def warning(self, text: str) -> None:
        messagebox.showwarning(APP_TITLE, text, parent=self.root)

    def error(self, text: str) -> None:
        messagebox.showerror(APP_TITLE, text, parent=self.root)
