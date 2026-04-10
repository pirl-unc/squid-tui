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


from datetime import datetime

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    DataTable,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from . import constants
from .constants import (
    ALL_JOBS,
    DISPLAY_COLUMNS,
    FIELD_TO_COLUMN,
    NODE_COLUMNS,
    PARTITION_COLUMNS,
    PARTITIONS,
    QUEUE_STATES,
    RUNNING_STATES,
    UNASSIGNED,
    SlurmJob,
)
from .screens import (
    ConfirmCancelScreen,
    JobDetailScreen,
    JobOutputScreen,
    MoveToListScreen,
    NewListScreen,
    NoteScreen,
    RefreshRateScreen,
)
from .slurm import (
    cancel_job,
    copy_to_clipboard,
    fetch_completed_jobs,
    fetch_jobs,
    fetch_nodes,
    fetch_partitions,
    fetch_recent_history,
    load_config,
    save_config,
)
from .widgets import SelectableDataTable, SelectionChanged, TwoRowFooter


class SquidApp(App):
    """SLURM job manager with kanban-style lists."""

    TITLE = "squid"
    SUB_TITLE = "Slurm QUeue Interactive Dashboard"

    BINDINGS = [
        # Primary actions (shown in footer)
        # priority=True so these fire before DataTable consumes the key
        Binding("n", "new_list", "New List", priority=True),
        Binding("d", "delete_list", "Delete List", priority=True),
        Binding("m", "move_job", "Move Job", priority=True),
        Binding("a", "add_note", "Add Note", priority=True),
        Binding("x", "remove_from_list", "Remove from List", priority=True),
        Binding("c", "cancel_job", "Cancel Job", priority=True),
        Binding("space", "toggle_select", "Select", priority=True),
        Binding("v", "toggle_select_mode", "Toggle Select Mode", priority=True),
        Binding("i", "view_detail", "Job Detail", priority=True),
        Binding("o", "view_output", "Job Output", priority=True),
        Binding("escape", "exit_select_mode", "Clear Selection", priority=True),
        Binding("y", "yank_ids", "Copy Job ID", priority=True),
        Binding("/", "search", "Search", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("s", "set_refresh", "Set Refresh", priority=True),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    #main-layout {
        height: 1fr;
    }

    #sidebar {
        width: 24;
        border-right: tall $primary-background;
        padding: 0;
    }

    #sidebar-title {
        text-style: bold;
        padding: 1 1 0 1;
        color: $text;
    }

    #list-view {
        height: auto;
        max-height: 50%;
    }

    #list-view > ListItem {
        padding: 0 1;
    }

    #cluster-title {
        text-style: bold;
        padding: 1 1 0 1;
        color: $text;
    }

    #cluster-view {
        height: auto;
    }

    #cluster-view > ListItem {
        padding: 0 1;
    }

    #job-area {
        width: 1fr;
    }

    #job-tabs {
        height: 1fr;
    }

    TabPane {
        padding: 0;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        padding: 0 1;
        color: $text-muted;
    }

    #loading-overlay {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-style: bold;
        color: $text-muted;
    }

    #loading-overlay.hidden {
        display: none;
    }

    #current-list-label {
        text-style: bold;
        padding: 0 1;
        margin-bottom: 0;
        color: $accent;
    }

    #search-input {
        display: none;
        height: 3;
        margin: 0 1;
    }

    #search-input.visible {
        display: block;
    }

    DataTable {
        height: 1fr;
    }

    .list-item-active {
        background: $accent 30%;
    }

    #partition-table, #node-table {
        display: none;
        height: 1fr;
    }

    #partition-table.visible, #node-table.visible {
        display: block;
    }
    """

    active_list: reactive[str] = reactive(ALL_JOBS)

    def __init__(self, refresh_interval: int = 30) -> None:
        super().__init__()
        self.config = load_config()
        self.jobs: list[SlurmJob] = []
        self.custom_lists: dict[str, list[str]] = self.config.get("lists", {})
        self.assignments: dict[str, str] = self.config.get("assignments", {})
        self.notes: dict[str, str] = self.config.get("notes", {})
        self.sort_column: str | None = None
        self.sort_reverse: bool = False
        self.selected_ids: set[str] = set()
        self.select_mode: bool = False
        self.filter_text: str = ""
        self.refresh_interval = refresh_interval
        self._refresh_timer: Timer | None = None

    # -- Compose --------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            with Vertical(id="sidebar"):
                yield Label("Lists", id="sidebar-title")
                yield ListView(id="list-view")
                yield Label("Cluster", id="cluster-title")
                yield ListView(id="cluster-view")
            with Vertical(id="job-area"):
                yield Label(f"  {ALL_JOBS}", id="current-list-label")
                yield Input(placeholder="Filter by job name...", id="search-input")
                yield Static("Fetching jobs from SLURM...", id="loading-overlay")
                with TabbedContent(id="job-tabs"):
                    with TabPane("Pending", id="tab-pending"):
                        yield SelectableDataTable(id="queue-table", cursor_type="row")
                    with TabPane("Active", id="tab-active"):
                        yield SelectableDataTable(id="running-table", cursor_type="row")
                    with TabPane("History", id="tab-history"):
                        yield SelectableDataTable(id="history-table", cursor_type="row")
                yield DataTable(id="partition-table", cursor_type="row")
                yield DataTable(id="node-table", cursor_type="row")
        yield Static("Loading...", id="status-bar")
        yield TwoRowFooter()

    # -- Lifecycle ------------------------------------------------------

    def on_mount(self) -> None:
        user = constants.SQUEUE_USER or "all"
        self.sub_title = f"Slurm QUeue Interactive Dashboard (user={user})"
        self._setup_table()
        self._rebuild_sidebar()
        self._setup_cluster_sidebar()
        self._select_sidebar_item(ALL_JOBS)
        # Hide tables until first data arrives
        self.query_one("#job-tabs", TabbedContent).display = False
        self.refresh_jobs()
        self._refresh_timer = self.set_interval(self.refresh_interval, self.refresh_jobs)

    def _setup_table(self) -> None:
        for table_id in ("queue-table", "running-table", "history-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            for col_name, width in DISPLAY_COLUMNS:
                table.add_column(col_name, key=col_name, width=width)
        ptable = self.query_one("#partition-table", DataTable)
        for col_name, width in PARTITION_COLUMNS:
            ptable.add_column(col_name, key=col_name, width=width)
        ntable = self.query_one("#node-table", DataTable)
        for col_name, width in NODE_COLUMNS:
            ntable.add_column(col_name, key=col_name, width=width)

    # -- Sidebar --------------------------------------------------------

    def _rebuild_sidebar(self) -> None:
        lv = self.query_one("#list-view", ListView)
        lv.clear()
        names = self._all_list_names()
        for name in names:
            count = self._count_jobs_in_list(name)
            lv.append(ListItem(Label(f"{name} ({count})"), name=name))

    def _all_list_names(self) -> list[str]:
        return [ALL_JOBS, UNASSIGNED] + sorted(self.custom_lists.keys())

    def _assigned_job_ids(self) -> set[str]:
        """IDs that appear in at least one custom list."""
        ids: set[str] = set()
        for jids in self.custom_lists.values():
            ids.update(jids)
        return ids

    def _is_active(self, job: SlurmJob) -> bool:
        return job.state in QUEUE_STATES or job.state in RUNNING_STATES

    def _count_jobs_in_list(self, list_name: str) -> int:
        if list_name == ALL_JOBS:
            return sum(1 for j in self.jobs if self._is_active(j))
        if list_name == UNASSIGNED:
            assigned = self._assigned_job_ids()
            return sum(1 for j in self.jobs if j.job_id not in assigned and self._is_active(j))
        assigned = set(self.custom_lists.get(list_name, []))
        return sum(1 for j in self.jobs if j.job_id in assigned)

    CLUSTER_ITEMS = ["Partitions", "Nodes"]

    def _setup_cluster_sidebar(self) -> None:
        cv = self.query_one("#cluster-view", ListView)
        cv.clear()
        for name in self.CLUSTER_ITEMS:
            cv.append(ListItem(Label(name), name=name))

    def _select_sidebar_item(self, name: str) -> None:
        lv = self.query_one("#list-view", ListView)
        names = self._all_list_names()
        if name in names:
            idx = names.index(name)
            if idx < len(lv.children):
                lv.index = idx

    @on(ListView.Selected, "#list-view")
    def on_list_selected(self, event: ListView.Selected) -> None:
        name = event.item.name
        if name:
            # Deselect cluster sidebar
            self.query_one("#cluster-view", ListView).index = None
            self.active_list = name

    @on(ListView.Selected, "#cluster-view")
    def on_cluster_selected(self, event: ListView.Selected) -> None:
        name = event.item.name
        if name:
            # Deselect list sidebar
            self.query_one("#list-view", ListView).index = None
            self.active_list = name

    def _show_cluster_view(self, name: str) -> None:
        """Show a cluster table (Partitions or Nodes), hide job tabs."""
        try:
            self.query_one("#job-tabs", TabbedContent).display = False
            ptable = self.query_one("#partition-table", DataTable)
            ntable = self.query_one("#node-table", DataTable)
            if name == "Partitions":
                ptable.add_class("visible")
                ntable.remove_class("visible")
            else:
                ptable.remove_class("visible")
                ntable.add_class("visible")
        except NoMatches:
            pass

    def _show_job_view(self) -> None:
        """Show job tabs, hide cluster tables."""
        try:
            self.query_one("#job-tabs", TabbedContent).display = True
            self.query_one("#partition-table", DataTable).remove_class("visible")
            self.query_one("#node-table", DataTable).remove_class("visible")
        except NoMatches:
            pass

    def watch_active_list(self, value: str) -> None:
        try:
            self.query_one("#current-list-label", Label).update(f"  {value}")
        except NoMatches:
            pass
        if value in self.CLUSTER_ITEMS:
            self._show_cluster_view(value)
            return
        self._show_job_view()
        self._populate_table()

    # -- Table ----------------------------------------------------------

    def _populate_table(self) -> None:
        visible = self._visible_jobs()

        # Classify
        queued = [j for j in visible if j.state in QUEUE_STATES]
        running = [j for j in visible if j.state in RUNNING_STATES]
        history = [j for j in visible if j.state not in QUEUE_STATES and j.state not in RUNNING_STATES]

        # Update tab labels with counts
        try:
            tabs = self.query_one("#job-tabs", TabbedContent)
            tabs.get_tab("tab-pending").label = f"Pending ({len(queued)})"
            tabs.get_tab("tab-active").label = f"Active ({len(running)})"
            tabs.get_tab("tab-history").label = f"History ({len(history)})"
        except (NoMatches, Exception):
            pass

        for table_id, jobs in (
            ("queue-table", queued),
            ("running-table", running),
            ("history-table", history),
        ):
            table = self.query_one(f"#{table_id}", DataTable)
            table.clear()

            if self.sort_column:
                field = None
                for f, c in FIELD_TO_COLUMN.items():
                    if c == self.sort_column:
                        field = f
                        break
                if field:
                    jobs.sort(key=lambda j: getattr(j, field, ""), reverse=self.sort_reverse)

            for job in jobs:
                marker = "●" if job.job_id in self.selected_ids else ""
                table.add_row(marker, *job.row(), key=job.job_id)

    def _visible_jobs(self) -> list[SlurmJob]:
        if self.active_list == ALL_JOBS:
            jobs = list(self.jobs)
        elif self.active_list == UNASSIGNED:
            assigned = self._assigned_job_ids()
            jobs = [j for j in self.jobs if j.job_id not in assigned]
        else:
            assigned_ids = set(self.custom_lists.get(self.active_list, []))
            jobs = [j for j in self.jobs if j.job_id in assigned_ids]

        if self.filter_text:
            jobs = [j for j in jobs if self.filter_text in j.name.lower() or self.filter_text in j.job_id]
        return jobs

    @staticmethod
    def _mb_to_gb(value: str) -> str:
        """Convert an MB string from sinfo to a human-readable GB string."""
        try:
            return f"{int(value) / 1024:.1f}"
        except (ValueError, TypeError):
            return value

    def _populate_partitions(self, partitions: list[dict[str, str]]) -> None:
        table = self.query_one("#partition-table", DataTable)
        table.clear()
        for p in partitions:
            table.add_row(
                p.get("partition", ""),
                p.get("avail", ""),
                p.get("timelimit", ""),
                p.get("nodes", ""),
                p.get("cpus", ""),
                self._mb_to_gb(p.get("memory", "")),
            )

    def _populate_nodes(self, nodes: list[dict[str, str]]) -> None:
        table = self.query_one("#node-table", DataTable)
        table.clear()
        for n in nodes:
            table.add_row(
                n.get("nodelist", ""),
                n.get("partition", ""),
                n.get("state", ""),
                n.get("cpus", ""),
                self._mb_to_gb(n.get("memory", "")),
                n.get("cpu_load", ""),
                self._mb_to_gb(n.get("free_mem", "")),
                n.get("features", ""),
            )

    @on(DataTable.HeaderSelected)
    def on_header_click(self, event: DataTable.HeaderSelected) -> None:
        col = str(event.column_key)
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._populate_table()

    # -- Data refresh ---------------------------------------------------

    @work(thread=True)
    def refresh_jobs(self) -> None:
        jobs = fetch_jobs(constants.SQUEUE_USER)
        live_ids = {j.job_id for j in jobs}

        # Find job IDs in custom lists that are no longer in squeue
        listed_ids: set[str] = set()
        for jids in self.custom_lists.values():
            listed_ids.update(jids)
        missing_ids = listed_ids - live_ids

        # Fetch listed completed jobs and recent history
        completed = fetch_completed_jobs(missing_ids)
        history = fetch_recent_history(constants.SQUEUE_USER)
        partitions = fetch_partitions()
        nodes = fetch_nodes()

        self.app.call_from_thread(self._apply_jobs, jobs, completed, history, partitions, nodes)

    def _apply_jobs(
        self,
        jobs: list[SlurmJob],
        completed: list[SlurmJob],
        history: list[SlurmJob],
        partitions: list[dict[str, str]],
        nodes: list[dict[str, str]] | None = None,
    ) -> None:
        # Merge: live jobs take priority, then listed completed, then history
        seen_ids: set[str] = set()
        all_jobs: list[SlurmJob] = []
        for job in jobs:
            seen_ids.add(job.job_id)
            all_jobs.append(job)
        for job in completed:
            if job.job_id not in seen_ids:
                seen_ids.add(job.job_id)
                all_jobs.append(job)
        for job in history:
            if job.job_id not in seen_ids:
                seen_ids.add(job.job_id)
                all_jobs.append(job)
        # Inject notes
        for job in all_jobs:
            job.note = self.notes.get(job.job_id, "")
        self.jobs = all_jobs
        self._populate_table()
        self._populate_partitions(partitions)
        if nodes is not None:
            self._populate_nodes(nodes)
        self._rebuild_sidebar()
        # Hide loading overlay, show tables
        try:
            overlay = self.query_one("#loading-overlay", Static)
            if not overlay.has_class("hidden"):
                overlay.add_class("hidden")
                if self.active_list in self.CLUSTER_ITEMS:
                    self._show_cluster_view(self.active_list)
                else:
                    self.query_one("#job-tabs", TabbedContent).display = True
        except NoMatches:
            pass
        n_active = len(jobs)
        n_history = len(all_jobs) - n_active
        now = datetime.now().strftime("%H:%M:%S")
        try:
            self.query_one("#status-bar", Static).update(
                f" {n_active} active + {n_history} history | refreshed {now} | auto-refresh {self.refresh_interval}s"
            )
        except NoMatches:
            pass

    def action_refresh(self) -> None:
        self.refresh_jobs()

    # Search
    def action_search(self) -> None:
        search_input = self.query_one("#search-input", Input)
        search_input.add_class("visible")
        search_input.focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value.strip().lower()
        self._populate_table()

    @on(Input.Submitted, "#search-input")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        # Keep filter active, move focus back to table
        self.query_one("#search-input", Input).remove_class("visible")
        # Focus the active tab's table
        tab_map = {
            "tab-pending": "queue-table",
            "tab-active": "running-table",
            "tab-history": "history-table",
        }
        try:
            tabs = self.query_one("#job-tabs", TabbedContent)
            table_id = tab_map.get(tabs.active, "queue-table")
            self.query_one(f"#{table_id}", DataTable).focus()
        except Exception:
            pass

    def action_set_refresh(self) -> None:
        self.push_screen(
            RefreshRateScreen(self.refresh_interval),
            callback=self._on_set_refresh,
        )

    def _on_set_refresh(self, value: int | None) -> None:
        if value is None:
            return
        self.refresh_interval = value
        if self._refresh_timer:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_interval(self.refresh_interval, self.refresh_jobs)
        try:
            self.query_one("#status-bar", Static).update(
                f" Refresh interval set to {value}s"
            )
        except NoMatches:
            pass

    # -- Selection ------------------------------------------------------

    def _get_focused_table(self) -> DataTable | None:
        for table_id in ("queue-table", "running-table", "history-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            if table.has_focus:
                return table
        return None

    def _get_cursor_job_id(self, table: DataTable | None = None) -> str | None:
        """Get the job ID at the current cursor position."""
        if table:
            if table.row_count > 0:
                try:
                    row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                    return str(row_key.value)
                except Exception:
                    pass
            return None

        # Try focused table first
        focused = self._get_focused_table()
        if focused and focused.row_count > 0:
            try:
                row_key, _ = focused.coordinate_to_cell_key(focused.cursor_coordinate)
                return str(row_key.value)
            except Exception:
                pass

        # Fallback: try table in the active tab
        tab_map = {
            "tab-pending": "queue-table",
            "tab-active": "running-table",
            "tab-history": "history-table",
        }
        try:
            tabs = self.query_one("#job-tabs", TabbedContent)
            active_tab = tabs.active
            if active_tab in tab_map:
                t = self.query_one(f"#{tab_map[active_tab]}", DataTable)
                if t.row_count > 0:
                    row_key, _ = t.coordinate_to_cell_key(t.cursor_coordinate)
                    return str(row_key.value)
        except Exception:
            pass

        return None

    def _get_effective_ids(self) -> list[str]:
        """Return selected IDs if any, otherwise the cursor job."""
        if self.selected_ids:
            return list(self.selected_ids)
        job_id = self._get_cursor_job_id()
        return [job_id] if job_id else []

    def _update_selection_markers(self) -> None:
        """Update the selection column without full repopulate."""
        for table_id in ("queue-table", "running-table", "history-table"):
            table = self.query_one(f"#{table_id}", DataTable)
            for row_key in table.rows:
                jid = str(row_key.value)
                marker = "●" if jid in self.selected_ids else ""
                try:
                    table.update_cell(row_key, "▸", marker)
                except Exception:
                    pass
        self._update_selection_status()

    def _update_selection_status(self) -> None:
        if self.selected_ids:
            try:
                self.query_one("#status-bar", Static).update(
                    f" {len(self.selected_ids)} job(s) selected"
                )
            except NoMatches:
                pass

    def _set_select_mode(self, enabled: bool) -> None:
        self.select_mode = enabled
        for table_id in ("queue-table", "running-table", "history-table"):
            try:
                table = self.query_one(f"#{table_id}", SelectableDataTable)
                table.select_mode = enabled
            except NoMatches:
                pass
        if enabled:
            # Select the current cursor row on entering select mode
            job_id = self._get_cursor_job_id()
            if job_id:
                self.selected_ids.add(job_id)
                self._update_selection_markers()
            try:
                self.query_one("#status-bar", Static).update(
                    " SELECT MODE — ↑↓ to extend, Space toggle, v/Esc to exit"
                )
            except NoMatches:
                pass
        else:
            self._update_selection_status()

    def action_toggle_select_mode(self) -> None:
        self._set_select_mode(not self.select_mode)

    def action_toggle_select(self) -> None:
        table = self._get_focused_table()
        job_id = self._get_cursor_job_id(table)
        if not job_id:
            return
        if job_id in self.selected_ids:
            self.selected_ids.discard(job_id)
        else:
            self.selected_ids.add(job_id)
        self._update_selection_markers()

    def action_exit_select_mode(self) -> None:
        # Close search if open
        search_input = self.query_one("#search-input", Input)
        if search_input.has_class("visible"):
            search_input.remove_class("visible")
            search_input.value = ""
            self.filter_text = ""
            self._populate_table()
            return
        if self.select_mode:
            self._set_select_mode(False)
        else:
            self.selected_ids.clear()
            self._update_selection_markers()

    def on_selection_changed(self, event: SelectionChanged) -> None:
        """Handle shift+arrow selection from SelectableDataTable."""
        table = event.table
        if table.row_count == 0:
            return
        job_id = self._get_cursor_job_id(table)
        if job_id:
            self.selected_ids.add(job_id)
        row = table.cursor_coordinate.row
        new_row = row + event.direction
        if 0 <= new_row < table.row_count:
            table.move_cursor(row=new_row)
            new_id = self._get_cursor_job_id(table)
            if new_id:
                self.selected_ids.add(new_id)
        self._update_selection_markers()

    # -- Actions --------------------------------------------------------

    # View detail (single job only)
    def action_view_detail(self) -> None:
        job_id = self._get_cursor_job_id()
        if job_id:
            self.push_screen(JobDetailScreen(job_id))

    # View job output (single job only)
    def action_view_output(self) -> None:
        job_id = self._get_cursor_job_id()
        if job_id:
            self.push_screen(JobOutputScreen(job_id))

    # Copy job ID(s) to clipboard
    def action_yank_ids(self) -> None:
        ids = self._get_effective_ids()
        if not ids:
            return
        text = "\n".join(ids) if len(ids) > 1 else ids[0]
        self._do_copy(text, len(ids))

    @work(thread=True)
    def _do_copy(self, text: str, count: int) -> None:
        success, msg = copy_to_clipboard(text)
        if success:
            display = f"Copied {count} job ID(s)" if count > 1 else f"Copied {text}"
        else:
            display = msg
        self.app.call_from_thread(self._show_copy_result, display)

    def _show_copy_result(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(f" {msg}")
        except NoMatches:
            pass

    # Cancel job(s)
    def action_cancel_job(self) -> None:
        ids = self._get_effective_ids()
        if not ids:
            return
        label = f"{len(ids)} job(s)" if len(ids) > 1 else f"job {ids[0]}"
        self.push_screen(
            ConfirmCancelScreen(label),
            callback=lambda confirmed: self._on_cancel_result(confirmed, ids),
        )

    def _on_cancel_result(self, confirmed: bool | None, ids: list[str] = None) -> None:
        if not confirmed or not ids:
            return
        for job_id in ids:
            self._do_cancel(job_id)
        self.selected_ids.clear()

    @work(thread=True)
    def _do_cancel(self, job_id: str) -> None:
        success, msg = cancel_job(job_id)
        self.app.call_from_thread(self._show_cancel_result, msg)
        if success:
            self.refresh_jobs()

    def _show_cancel_result(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(f" {msg}")
        except NoMatches:
            pass

    # New list
    def action_new_list(self) -> None:
        self.push_screen(NewListScreen(), callback=self._on_new_list)

    def _on_new_list(self, name: str | None) -> None:
        if not name or name in (ALL_JOBS, UNASSIGNED, PARTITIONS):
            return
        if name not in self.custom_lists:
            self.custom_lists[name] = []
            self._save()
            self._rebuild_sidebar()
            self.active_list = name
            self._select_sidebar_item(name)

    # Delete list
    def action_delete_list(self) -> None:
        if self.active_list in (ALL_JOBS, UNASSIGNED, PARTITIONS):
            return
        name = self.active_list
        if name in self.custom_lists:
            del self.custom_lists[name]
            self._save()
            self.active_list = ALL_JOBS
            self._rebuild_sidebar()
            self._select_sidebar_item(ALL_JOBS)

    # Move job(s) to list
    def action_move_job(self) -> None:
        ids = self._get_effective_ids()
        if not ids:
            return
        lists = self._all_list_names()
        self.push_screen(
            MoveToListScreen(lists, self.active_list),
            callback=lambda target: self._on_move(ids, target),
        )

    def _on_move(self, job_ids: list[str], target: str | None) -> None:
        if not target:
            return
        for job_id in job_ids:
            # Remove from all custom lists first
            for list_name in self.custom_lists:
                if job_id in self.custom_lists[list_name]:
                    self.custom_lists[list_name].remove(job_id)
            # Add to target (unless it's All Jobs)
            if target != ALL_JOBS:
                if target not in self.custom_lists:
                    self.custom_lists[target] = []
                self.custom_lists[target].append(job_id)

        self.selected_ids.clear()
        self._save()
        self._populate_table()
        self._rebuild_sidebar()

    # Add note (single job only)
    def action_add_note(self) -> None:
        job_id = self._get_cursor_job_id()
        if not job_id:
            return
        current = self.notes.get(job_id, "")
        self.push_screen(
            NoteScreen(job_id, current),
            callback=lambda val: self._on_note(job_id, val),
        )

    def _on_note(self, job_id: str, value: str | None) -> None:
        if value is None:
            return
        if value:
            self.notes[job_id] = value
        elif job_id in self.notes:
            del self.notes[job_id]
        for job in self.jobs:
            if job.job_id == job_id:
                job.note = value
                break
        self._save()
        self._populate_table()

    # Remove from list
    def action_remove_from_list(self) -> None:
        ids = self._get_effective_ids()
        if not ids or self.active_list in (ALL_JOBS, UNASSIGNED):
            return
        list_name = self.active_list
        if list_name in self.custom_lists:
            for job_id in ids:
                if job_id in self.custom_lists[list_name]:
                    self.custom_lists[list_name].remove(job_id)
            self.selected_ids.clear()
            self._save()
            self._populate_table()
            self._rebuild_sidebar()

    # -- Persistence ----------------------------------------------------

    def _save(self) -> None:
        self.config["lists"] = self.custom_lists
        self.config["notes"] = self.notes
        save_config(self.config)


def run(user: str | None = None, refresh_interval: int = 180) -> None:
    constants.SQUEUE_USER = user
    app = SquidApp(refresh_interval=refresh_interval)
    app.run()
