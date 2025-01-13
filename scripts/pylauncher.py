# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "ducktools-pythonfinder>=0.6.8",
#     "textual~=1.0",
# ]
# ///

import signal
import subprocess

from ducktools.pythonfinder import list_python_installs

from textual.app import App
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header


class IgnoreSignals:
    @staticmethod
    def null_handler(signum, frame):
        # This just ignores signals, used to ignore in the parent process temporarily
        # The child process will still receive the signals.
        pass

    def __init__(self, signums: list[int]):
        self.old_signals = {}
        self.signums = signums

    def __enter__(self):
        if self.old_signals:
            raise RuntimeError("ignore_signals is not reentrant")

        for signum in self.signums:
            self.old_signals[signum] = signal.signal(signum, self.null_handler)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for signum, handler in self.old_signals.items():
            signal.signal(signum, handler)


def ignore_keyboardinterrupt():
    return IgnoreSignals([signal.SIGINT])


class ManagerApp(App):
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="enter", action="launch", description="Launch REPL", priority=True),
    ]

    def compose(self):
        yield Header()
        yield DataTable()
        yield Footer()

    def action_launch(self):
        table = self.query_one(DataTable)

        row = table.coordinate_to_cell_key(table.cursor_coordinate)
        python_exe = row.row_key.value

        # Suspend the app and launch python
        # Ignore keyboard interrupts otherwise the program will exit when this exits.
        with ignore_keyboardinterrupt(), self.suspend():
            subprocess.run([python_exe])

        # Redraw
        self.refresh()

    def on_mount(self):
        self.title = "Ducktools: PyLauncher"
        table = self.query_one(DataTable)
        table.cursor_type = "row"
        table.add_columns("Version", "Managed By", "Implementation", "Path")
        for p in list_python_installs():
            table.add_row(p.version_str, p.managed_by, p.implementation, p.executable, key=p.executable)


if __name__ == "__main__":
    app = ManagerApp()
    app.run()
