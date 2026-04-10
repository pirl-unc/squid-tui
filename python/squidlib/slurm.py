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


import json
import os
import platform
import re
import shutil
import subprocess
from datetime import datetime, timedelta

from .constants import (
    CONFIG_PATH,
    QUEUE_STATES,
    RUNNING_STATES,
    SINFO_FIELDS,
    SINFO_FORMAT,
    SINFO_NODE_FIELDS,
    SINFO_NODE_FORMAT,
    SQUEUE_FIELDS,
    SQUEUE_FORMAT,
    SlurmJob,
)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"lists": {}, "assignments": {}}


def save_config(config: dict) -> None:
    fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(config, f, indent=2)


def fetch_jobs(user: str | None = None) -> list[SlurmJob]:
    """Fetch jobs from squeue."""
    cmd = ["squeue", f"--format={SQUEUE_FORMAT}", "--noheader"]
    if user:
        cmd.extend(["--user", user])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    jobs = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= len(SQUEUE_FIELDS):
            job = SlurmJob(**{k: v.strip() for k, v in zip(SQUEUE_FIELDS, parts)})
            jobs.append(job)
    return jobs


def fetch_completed_jobs(job_ids: set[str]) -> list[SlurmJob]:
    """Fetch info for completed/gone jobs via sacct."""
    if not job_ids:
        return []
    try:
        result = subprocess.run(
            [
                "sacct",
                "--allocations",
                "-j",
                ",".join(job_ids),
                "--format=JobID,Partition,JobName,User,State,Elapsed,Timelimit,AllocCPUS,ReqMem,NodeList",
                "--parsable2",
                "--noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    jobs = []
    seen = set()
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 10:
            continue
        job_id = parts[0].split(".")[0]  # strip .batch / .extern suffixes
        if job_id not in job_ids or job_id in seen:
            continue
        seen.add(job_id)
        state = parts[4].split()[0]  # Handle "CANCELLED by 12345"
        jobs.append(SlurmJob(
            job_id=job_id,
            partition=parts[1],
            name=parts[2],
            user=parts[3],
            state=state,
            time=parts[5],
            time_limit=parts[6],
            cpus=parts[7],
            memory=parts[8],
            nodelist=parts[9],
        ))
    return jobs


def fetch_recent_history(user: str | None = None, days: int = 1) -> list[SlurmJob]:
    """Fetch recently completed/failed/cancelled jobs via sacct."""
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cmd = [
        "sacct",
        "-S", start,
        "--format=JobID,Partition,JobName,User,State,Elapsed,Timelimit,AllocCPUS,ReqMem,NodeList",
        "--parsable2",
        "--noheader",
        "-X",  # no job steps, main jobs only
    ]
    if user:
        cmd.extend(["--user", user])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    jobs = []
    seen = set()
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) < 10:
            continue
        job_id = parts[0].split(".")[0]
        if job_id in seen:
            continue
        seen.add(job_id)
        state = parts[4].split()[0]  # Handle "CANCELLED by 12345" -> "CANCELLED"
        # Skip active states — we already have those from squeue
        if state in QUEUE_STATES or state in RUNNING_STATES:
            continue
        jobs.append(SlurmJob(
            job_id=job_id,
            partition=parts[1],
            name=parts[2],
            user=parts[3],
            state=state,
            time=parts[5],
            time_limit=parts[6],
            cpus=parts[7],
            memory=parts[8],
            nodelist=parts[9],
        ))
    return jobs


def fetch_job_detail(job_id: str) -> str:
    """Fetch detailed info via scontrol and sacct."""
    sections = []

    # scontrol show job
    try:
        result = subprocess.run(
            ["scontrol", "show", "job", job_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            sections.append("── scontrol show job ──\n" + result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        sections.append("scontrol: unavailable")

    # sacct
    try:
        result = subprocess.run(
            [
                "sacct",
                "-j",
                job_id,
                "--format=JobID,JobName,Partition,State,ExitCode,Elapsed,MaxRSS,ReqMem,AllocCPUS,NodeList",
                "--parsable2",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            sections.append("── sacct ──\n" + result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        sections.append("sacct: unavailable")

    return "\n\n".join(sections) if sections else "No details available."


def cancel_job(job_id: str) -> tuple[bool, str]:
    """Cancel a job. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["scancel", job_id], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, f"Job {job_id} cancelled."
        return False, f"scancel failed: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, "scancel not found."
    except subprocess.TimeoutExpired:
        return False, "scancel timed out."


def fetch_job_output_paths(job_id: str) -> tuple[str | None, str | None]:
    """Parse StdOut/StdErr paths from scontrol show job."""
    try:
        result = subprocess.run(
            ["scontrol", "show", "job", job_id],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None, None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None

    stdout_match = re.search(r"StdOut=(\S+)", result.stdout)
    stderr_match = re.search(r"StdErr=(\S+)", result.stdout)
    return (
        stdout_match.group(1) if stdout_match else None,
        stderr_match.group(1) if stderr_match else None,
    )


def read_file_tail(path: str, lines: int = 100) -> str:
    """Read the last N lines of a file using tail."""
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
        return f"Cannot read {path}: {result.stderr.strip()}"
    except FileNotFoundError:
        return "tail command not found"
    except subprocess.TimeoutExpired:
        return f"Reading {path} timed out"


def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to system clipboard. Returns (success, message)."""
    if platform.system() == "Darwin":
        cmd = ["pbcopy"]
    elif shutil.which("xclip"):
        cmd = ["xclip", "-selection", "clipboard"]
    elif shutil.which("xsel"):
        cmd = ["xsel", "--clipboard", "--input"]
    else:
        return False, "No clipboard tool found (need xclip, xsel, or pbcopy)"
    try:
        result = subprocess.run(
            cmd, input=text, text=True, capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return True, f"Copied: {text}"
        return False, f"Clipboard failed: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return False, "Clipboard command timed out"


def fetch_partitions() -> list[dict[str, str]]:
    """Fetch partition info from sinfo."""
    cmd = ["sinfo", f"--format={SINFO_FORMAT}", "--noheader"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    partitions = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= len(SINFO_FIELDS):
            partitions.append({k: v.strip() for k, v in zip(SINFO_FIELDS, parts)})
    return partitions


def fetch_nodes() -> list[dict[str, str]]:
    """Fetch per-node info from sinfo -N."""
    cmd = ["sinfo", "-N", f"--format={SINFO_NODE_FORMAT}", "--noheader"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    nodes = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= len(SINFO_NODE_FIELDS):
            nodes.append({k: v.strip() for k, v in zip(SINFO_NODE_FIELDS, parts)})
    return nodes
