# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "ducktools-pythonfinder>=0.6.8",
#     "textual~=1.0",
# ]
# ///

import subprocess

from ducktools.pythonfinder import list_python_installs

from textual.app import App
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header


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
        with self.suspend():
            subprocess.run(python_exe)

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
