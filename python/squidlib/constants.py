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


from dataclasses import dataclass
from pathlib import Path

from rich.text import Text


CONFIG_PATH = Path.home() / ".squid.json"
ALL_JOBS = "All Jobs"
UNASSIGNED = "Unassigned"
PARTITIONS = "Partitions"
SQUEUE_USER = None  # Populated at startup

QUEUE_STATES = {"PENDING", "REQUEUED"}
RUNNING_STATES = {"RUNNING", "CONFIGURING", "COMPLETING", "SUSPENDED"}

SQUEUE_FORMAT = "%i|%P|%j|%u|%T|%M|%l|%C|%m|%N|%r"
SQUEUE_FIELDS = [
    "job_id",
    "partition",
    "name",
    "user",
    "state",
    "time",
    "time_limit",
    "cpus",
    "memory",
    "nodelist",
    "reason",
]

DISPLAY_COLUMNS = [
    ("▸", 3),
    ("Job ID", 10),
    ("Partition", 12),
    ("Name", 40),
    ("State", 10),
    ("Time", 12),
    ("Limit", 12),
    ("CPUs", 6),
    ("Memory", 10),
    ("Node", 16),
    ("Notes", 30),
]

FIELD_TO_COLUMN = {
    "job_id": "Job ID",
    "partition": "Partition",
    "name": "Name",
    "state": "State",
    "time": "Time",
    "time_limit": "Limit",
    "cpus": "CPUs",
    "memory": "Memory",
    "nodelist": "Node",
    "note": "Notes",
}

STATE_STYLES = {
    "RUNNING": "green",
    "CONFIGURING": "green",
    "COMPLETING": "green",
    "PENDING": "yellow",
    "REQUEUED": "yellow",
    "SUSPENDED": "yellow",
    "COMPLETED": "blue",
    "FAILED": "red bold",
    "TIMEOUT": "red",
    "OUT_OF_MEMORY": "red",
    "NODE_FAIL": "red",
    "CANCELLED": "magenta",
    "PREEMPTED": "magenta dim",
}

SINFO_FORMAT = "%P|%a|%l|%D|%C|%m"
SINFO_FIELDS = ["partition", "avail", "timelimit", "nodes", "cpus", "memory"]
PARTITION_COLUMNS = [
    ("Partition", 16),
    ("Avail", 8),
    ("Timelimit", 12),
    ("Nodes", 8),
    ("CPUs (Alloc/Idle/Other/Total)", 30),
    ("Memory (GB)", 12),
]

SINFO_NODE_FORMAT = "%N|%P|%T|%C|%m|%O|%e|%f"
SINFO_NODE_FIELDS = ["nodelist", "partition", "state", "cpus", "memory", "cpu_load", "free_mem", "features"]
NODE_COLUMNS = [
    ("Node", 20),
    ("Partition", 14),
    ("State", 14),
    ("CPUs (Alloc/Idle/Other/Total)", 30),
    ("Memory (GB)", 12),
    ("CPU Load", 10),
    ("Free Mem (GB)", 14),
    ("Features", 20),
]


@dataclass
class SlurmJob:
    job_id: str = ""
    partition: str = ""
    name: str = ""
    user: str = ""
    state: str = ""
    time: str = ""
    time_limit: str = ""
    cpus: str = ""
    memory: str = ""
    nodelist: str = ""
    reason: str = ""
    note: str = ""

    def row(self) -> tuple:
        style = STATE_STYLES.get(self.state, "")
        state_text = Text(self.state, style=style) if style else self.state
        return (
            self.job_id,
            self.partition,
            self.name,
            state_text,
            self.time,
            self.time_limit,
            self.cpus,
            self.memory,
            self.nodelist,
            self.note,
        )
