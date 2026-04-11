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


from math import ceil

from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static


class SelectionChanged(Message):
    """Posted when shift+arrow selection happens."""
    def __init__(self, table: DataTable, direction: int) -> None:
        super().__init__()
        self.table = table
        self.direction = direction  # +1 down, -1 up


class SelectableDataTable(DataTable):
    """DataTable that posts SelectionChanged when in select mode."""

    select_mode: bool = False

    def _on_key(self, event) -> None:
        if self.select_mode and event.key in ("down", "up"):
            direction = +1 if event.key == "down" else -1
            self.post_message(SelectionChanged(self, direction))
            event.prevent_default()
            event.stop()
            return
        super()._on_key(event)


class FooterButton(Static):
    """A single clickable footer binding."""

    DEFAULT_CSS = """
    FooterButton {
        width: auto;
        height: 1;
        background: $panel;
        padding: 0 1 0 0;
    }
    FooterButton:hover {
        background: $panel-lighten-1;
    }
    """

    def __init__(self, key: str, action: str, description: str) -> None:
        super().__init__()
        self.key = key
        self.action = action
        self.description = description

    def render(self) -> Text:
        return Text.assemble(
            (f" {self.key} ", "bold yellow on black"),
            (f" {self.description} ", "#b0b0b0"),
        )

    async def on_click(self) -> None:
        await self.app.run_action(self.action)


class TwoRowFooter(Widget):
    """A two-row footer displaying clickable key bindings."""

    DEFAULT_CSS = """
    TwoRowFooter {
        dock: bottom;
        height: 2;
        background: $panel;
    }
    TwoRowFooter Horizontal {
        height: 1;
        background: $panel;
    }
    """

    def compose(self) -> ComposeResult:
        bindings = [
            b for b in self.app.active_bindings.values()
            if b.binding.show
        ]
        mid = ceil(len(bindings) / 2)
        with Horizontal():
            for b in bindings[:mid]:
                yield FooterButton(b.binding.key_display or b.binding.key, b.binding.action, b.binding.description)
        with Horizontal():
            for b in bindings[mid:]:
                yield FooterButton(b.binding.key_display or b.binding.key, b.binding.action, b.binding.description)
