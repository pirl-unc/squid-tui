# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .slurm import fetch_job_detail, fetch_job_output_paths, read_file_tail


class JobDetailScreen(ModalScreen[None]):
    """Show job details in a modal."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    JobDetailScreen {
        align: center middle;
    }
    #detail-container {
        width: 90%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #detail-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #detail-text {
        overflow-y: auto;
        height: 1fr;
    }
    #detail-close {
        dock: bottom;
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, job_id: str) -> None:
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield Label(f"Job {self.job_id} — Details", id="detail-title")
            yield Static("Loading...", id="detail-text")
            yield Button("Close [Esc]", id="detail-close", variant="default")

    def on_mount(self) -> None:
        self.load_details()

    @work(thread=True)
    def load_details(self) -> None:
        detail = fetch_job_detail(self.job_id)
        self.app.call_from_thread(self._set_detail, detail)

    def _set_detail(self, text: str) -> None:
        try:
            self.query_one("#detail-text", Static).update(text)
        except NoMatches:
            pass

    @on(Button.Pressed, "#detail-close")
    def close_modal(self) -> None:
        self.dismiss()


class JobOutputScreen(ModalScreen[None]):
    """Show job stdout/stderr output in a modal."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    JobOutputScreen {
        align: center middle;
    }
    #output-container {
        width: 90%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #output-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #output-text {
        overflow-y: auto;
        height: 1fr;
    }
    #output-close {
        dock: bottom;
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, job_id: str) -> None:
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        with Vertical(id="output-container"):
            yield Label(f"Job {self.job_id} — Output", id="output-title")
            yield Static("Loading...", id="output-text")
            yield Button("Close [Esc]", id="output-close", variant="default")

    def on_mount(self) -> None:
        self.load_output()

    @work(thread=True)
    def load_output(self) -> None:
        stdout_path, stderr_path = fetch_job_output_paths(self.job_id)
        sections = []
        if stdout_path:
            sections.append(f"── StdOut: {stdout_path} ──\n{read_file_tail(stdout_path)}")
        else:
            sections.append("── StdOut: path not found ──")
        if stderr_path:
            sections.append(f"── StdErr: {stderr_path} ──\n{read_file_tail(stderr_path)}")
        else:
            sections.append("── StdErr: path not found ──")
        text = "\n\n".join(sections)
        self.app.call_from_thread(self._set_output, text)

    def _set_output(self, text: str) -> None:
        try:
            self.query_one("#output-text", Static).update(text)
        except NoMatches:
            pass

    @on(Button.Pressed, "#output-close")
    def close_modal(self) -> None:
        self.dismiss()


class ConfirmCancelScreen(ModalScreen[bool]):
    """Confirm job cancellation."""

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "deny", "No"),
        Binding("escape", "deny", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmCancelScreen {
        align: center middle;
    }
    #confirm-box {
        width: 50;
        height: auto;
        max-height: 12;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #confirm-label {
        margin-bottom: 1;
    }
    """

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Label(f"Cancel {self.label}?", id="confirm-label")
            with Horizontal():
                yield Button("Yes (y)", id="yes-btn", variant="error")
                yield Button("No (n)", id="no-btn", variant="default")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#yes-btn")
    def yes_pressed(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no-btn")
    def no_pressed(self) -> None:
        self.dismiss(False)


class NewListScreen(ModalScreen[str | None]):
    """Create a new list."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    NewListScreen {
        align: center middle;
    }
    #newlist-box {
        width: 50;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #newlist-label {
        margin-bottom: 1;
    }
    #newlist-input {
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="newlist-box"):
            yield Label("New list name:", id="newlist-label")
            yield Input(placeholder="e.g. Priority, Pipeline A, Done", id="newlist-input")
            with Horizontal():
                yield Button("Create", id="create-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    @on(Input.Submitted, "#newlist-input")
    def submit_input(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    @on(Button.Pressed, "#create-btn")
    def create_pressed(self) -> None:
        value = self.query_one("#newlist-input", Input).value.strip()
        self.dismiss(value if value else None)

    @on(Button.Pressed, "#cancel-btn")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class MoveToListScreen(ModalScreen[str | None]):
    """Pick a list to move a job into."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    MoveToListScreen {
        align: center middle;
    }
    #move-box {
        width: 40;
        max-height: 20;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #move-label {
        margin-bottom: 1;
    }
    """

    def __init__(self, lists: list[str], current_list: str) -> None:
        super().__init__()
        self.lists = lists
        self.current_list = current_list

    def compose(self) -> ComposeResult:
        with Vertical(id="move-box"):
            yield Label("Move to list:", id="move-label")
            options = []
            for name in self.lists:
                suffix = " (current)" if name == self.current_list else ""
                options.append(Option(f"{name}{suffix}"))
            yield OptionList(*options, id="move-options")
            yield Button("Cancel", id="move-cancel", variant="default")

    @on(OptionList.OptionSelected, "#move-options")
    def option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = event.option_index
        if 0 <= idx < len(self.lists):
            self.dismiss(self.lists[idx])

    @on(Button.Pressed, "#move-cancel")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class RefreshRateScreen(ModalScreen[int | None]):
    """Set auto-refresh interval."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    RefreshRateScreen {
        align: center middle;
    }
    #refresh-box {
        width: 50;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #refresh-label {
        margin-bottom: 1;
    }
    #refresh-input {
        margin-bottom: 1;
    }
    #set-btn {
        margin-right: 1;
    }
    """

    def __init__(self, current: int) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="refresh-box"):
            yield Label(f"Refresh interval in seconds (current: {self.current}):", id="refresh-label")
            yield Input(placeholder=str(self.current), id="refresh-input", type="integer")
            with Horizontal():
                yield Button("Set", id="set-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="default")

    @on(Input.Submitted, "#refresh-input")
    def submit_input(self, event: Input.Submitted) -> None:
        self._try_dismiss(event.value)

    @on(Button.Pressed, "#set-btn")
    def set_pressed(self) -> None:
        self._try_dismiss(self.query_one("#refresh-input", Input).value)

    @on(Button.Pressed, "#cancel-btn")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def _try_dismiss(self, value: str) -> None:
        try:
            val = int(value.strip())
            if val >= 1:
                self.dismiss(val)
        except (ValueError, AttributeError):
            pass


class NoteScreen(ModalScreen[str | None]):
    """Add/edit a note for a job."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    NoteScreen {
        align: center middle;
    }
    #note-box {
        width: 60;
        height: auto;
        max-height: 15;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #note-label {
        margin-bottom: 1;
    }
    #note-input {
        margin-bottom: 1;
    }
    """

    def __init__(self, job_id: str, current_note: str) -> None:
        super().__init__()
        self.job_id = job_id
        self.current_note = current_note

    def compose(self) -> ComposeResult:
        with Vertical(id="note-box"):
            yield Label(f"Note for job {self.job_id}:", id="note-label")
            yield Input(value=self.current_note, placeholder="Enter note...", id="note-input")
            with Horizontal():
                yield Button("Save", id="save-btn", variant="primary")
                yield Button("Clear", id="clear-btn", variant="warning")
                yield Button("Cancel", id="cancel-btn", variant="default")

    @on(Input.Submitted, "#note-input")
    def submit_input(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    @on(Button.Pressed, "#save-btn")
    def save_pressed(self) -> None:
        self.dismiss(self.query_one("#note-input", Input).value)

    @on(Button.Pressed, "#clear-btn")
    def clear_pressed(self) -> None:
        self.dismiss("")

    @on(Button.Pressed, "#cancel-btn")
    def cancel_pressed(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
