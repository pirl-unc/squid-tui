#!/usr/bin/env python3
"""
Squid demo with simulated SLURM data.

Run:  PYTHONPATH=python python examples/demo.py

Screenshot:
    python examples/demo.py --screenshot screenshots/demo.png

This launches squid with fake job and partition data so you can take
screenshots without needing a real SLURM cluster.
"""

import argparse
import sys
from pathlib import Path

from squidlib.app import SquidApp
from squidlib.constants import SlurmJob

# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FAKE_PARTITIONS = [
    {"partition": "gpu", "avail": "up", "timelimit": "7-00:00:00", "nodes": "12", "cpus": "96/288/0/384", "memory": "192000"},
    {"partition": "cpu", "avail": "up", "timelimit": "3-00:00:00", "nodes": "48", "cpus": "512/1024/0/1536", "memory": "131072"},
    {"partition": "highmem", "avail": "up", "timelimit": "2-00:00:00", "nodes": "4", "cpus": "32/96/0/128", "memory": "512000"},
    {"partition": "quick", "avail": "up", "timelimit": "04:00:00", "nodes": "20", "cpus": "80/240/0/320", "memory": "65536"},
    {"partition": "debug", "avail": "up", "timelimit": "01:00:00", "nodes": "2", "cpus": "8/24/0/32", "memory": "32768"},
]

FAKE_JOBS = [
    # Pending jobs
    SlurmJob(job_id="4810231", partition="gpu", name="train_resnet50_imagenet", user="jinseok", state="PENDING", time="0:00", time_limit="2-00:00:00", cpus="8", memory="64G", nodelist="", reason="Priority"),
    SlurmJob(job_id="4810245", partition="gpu", name="finetune_llama3_lora", user="jinseok", state="PENDING", time="0:00", time_limit="7-00:00:00", cpus="4", memory="128G", nodelist="", reason="Resources"),
    SlurmJob(job_id="4810302", partition="cpu", name="preprocess_rnaseq_batch2", user="jinseok", state="PENDING", time="0:00", time_limit="12:00:00", cpus="16", memory="32G", nodelist="", reason="Priority"),
    SlurmJob(job_id="4810318", partition="highmem", name="genome_assembly_hifi", user="jinseok", state="PENDING", time="0:00", time_limit="2-00:00:00", cpus="32", memory="256G", nodelist="", reason="Resources"),
    SlurmJob(job_id="4810401", partition="gpu", name="eval_diffusion_model", user="jinseok", state="PENDING", time="0:00", time_limit="1-00:00:00", cpus="4", memory="48G", nodelist="", reason="Priority"),

    # Running jobs
    SlurmJob(job_id="4809876", partition="gpu", name="train_imgthla", user="jinseok", state="RUNNING", time="14:32:07", time_limit="1-00:00:00", cpus="4", memory="32G", nodelist="gpu-node03", reason="None"),
    SlurmJob(job_id="4809912", partition="cpu", name="variant_calling_wgs", user="jinseok", state="RUNNING", time="6:45:21", time_limit="1-00:00:00", cpus="16", memory="64G", nodelist="cpu-node12", reason="None"),
    SlurmJob(job_id="4809945", partition="gpu", name="inference_bert_ner", user="jinseok", state="RUNNING", time="2:18:44", time_limit="04:00:00", cpus="2", memory="16G", nodelist="gpu-node07", reason="None"),
    SlurmJob(job_id="4809988", partition="cpu", name="star_alignment_batch1", user="jinseok", state="RUNNING", time="9:12:33", time_limit="12:00:00", cpus="8", memory="48G", nodelist="cpu-node05", reason="None"),
    SlurmJob(job_id="4810015", partition="highmem", name="de_novo_assembly_pb", user="jinseok", state="RUNNING", time="1-02:44:15", time_limit="2-00:00:00", cpus="32", memory="256G", nodelist="highmem-node02", reason="None"),
    SlurmJob(job_id="4810102", partition="gpu", name="gan_training_celeba", user="jinseok", state="RUNNING", time="22:05:11", time_limit="2-00:00:00", cpus="8", memory="64G", nodelist="gpu-node01", reason="None"),

    # History (completed/failed/cancelled)
    SlurmJob(job_id="4809501", partition="gpu", name="train_unet_segmentation", user="jinseok", state="COMPLETED", time="23:44:12", time_limit="1-00:00:00", cpus="4", memory="32G", nodelist="gpu-node05"),
    SlurmJob(job_id="4809422", partition="cpu", name="fastqc_analysis_all", user="jinseok", state="COMPLETED", time="1:22:05", time_limit="04:00:00", cpus="8", memory="16G", nodelist="cpu-node08"),
    SlurmJob(job_id="4809388", partition="gpu", name="pytorch_distributed_ddp", user="jinseok", state="FAILED", time="0:03:22", time_limit="1-00:00:00", cpus="16", memory="128G", nodelist="gpu-node02"),
    SlurmJob(job_id="4809301", partition="cpu", name="salmon_quant_batch3", user="jinseok", state="COMPLETED", time="3:15:47", time_limit="06:00:00", cpus="12", memory="24G", nodelist="cpu-node15"),
    SlurmJob(job_id="4809210", partition="gpu", name="stable_diffusion_train", user="jinseok", state="TIMEOUT", time="2-00:00:00", time_limit="2-00:00:00", cpus="8", memory="80G", nodelist="gpu-node04"),
    SlurmJob(job_id="4809155", partition="cpu", name="kallisto_pseudoalign", user="jinseok", state="COMPLETED", time="0:45:18", time_limit="02:00:00", cpus="4", memory="8G", nodelist="cpu-node22"),
    SlurmJob(job_id="4809088", partition="highmem", name="megahit_metagenome", user="jinseok", state="CANCELLED", time="5:30:00", time_limit="1-00:00:00", cpus="16", memory="192G", nodelist="highmem-node01"),
    SlurmJob(job_id="4808990", partition="gpu", name="alphafold_predict", user="jinseok", state="COMPLETED", time="8:12:33", time_limit="12:00:00", cpus="8", memory="64G", nodelist="gpu-node06"),
    SlurmJob(job_id="4808877", partition="cpu", name="cellranger_count", user="jinseok", state="OUT_OF_MEMORY", time="2:44:19", time_limit="06:00:00", cpus="8", memory="32G", nodelist="cpu-node03"),
]

FAKE_NOTES = {
    "4809876": "Check tensorboard for loss curves",
    "4810231": "Waiting for gpu-node01 to free up",
    "4809388": "OOM error — need to reduce batch size",
    "4810245": "Using LoRA rank=16, lr=2e-4",
}

FAKE_LISTS = {
    "ML Training": ["4810231", "4809876", "4810102", "4810245", "4810401"],
    "Bioinformatics": ["4809912", "4809988", "4810015", "4810302", "4810318"],
}

FAKE_NODES = [
    {"nodelist": "gpu-node01", "partition": "gpu", "state": "mixed", "cpus": "6/2/0/8", "memory": "192000", "cpu_load": "5.82", "free_mem": "45200", "features": "a100,nvlink"},
    {"nodelist": "gpu-node02", "partition": "gpu", "state": "idle", "cpus": "0/8/0/8", "memory": "192000", "cpu_load": "0.01", "free_mem": "188400", "features": "a100,nvlink"},
    {"nodelist": "gpu-node03", "partition": "gpu", "state": "mixed", "cpus": "4/4/0/8", "memory": "192000", "cpu_load": "3.91", "free_mem": "120800", "features": "a100,nvlink"},
    {"nodelist": "gpu-node04", "partition": "gpu", "state": "idle", "cpus": "0/8/0/8", "memory": "192000", "cpu_load": "0.00", "free_mem": "190100", "features": "a100,nvlink"},
    {"nodelist": "gpu-node05", "partition": "gpu", "state": "idle", "cpus": "0/8/0/8", "memory": "192000", "cpu_load": "0.00", "free_mem": "191500", "features": "a100,nvlink"},
    {"nodelist": "gpu-node06", "partition": "gpu", "state": "allocated", "cpus": "8/0/0/8", "memory": "192000", "cpu_load": "7.95", "free_mem": "32100", "features": "a100,nvlink"},
    {"nodelist": "gpu-node07", "partition": "gpu", "state": "mixed", "cpus": "2/6/0/8", "memory": "192000", "cpu_load": "1.88", "free_mem": "165300", "features": "a100,nvlink"},
    {"nodelist": "cpu-node03", "partition": "cpu", "state": "allocated", "cpus": "32/0/0/32", "memory": "131072", "cpu_load": "31.20", "free_mem": "8400", "features": "epyc"},
    {"nodelist": "cpu-node05", "partition": "cpu", "state": "mixed", "cpus": "8/24/0/32", "memory": "131072", "cpu_load": "7.85", "free_mem": "78900", "features": "epyc"},
    {"nodelist": "cpu-node08", "partition": "cpu", "state": "idle", "cpus": "0/32/0/32", "memory": "131072", "cpu_load": "0.00", "free_mem": "129500", "features": "epyc"},
    {"nodelist": "cpu-node12", "partition": "cpu", "state": "mixed", "cpus": "16/16/0/32", "memory": "131072", "cpu_load": "15.70", "free_mem": "62300", "features": "epyc"},
    {"nodelist": "cpu-node15", "partition": "cpu", "state": "idle", "cpus": "0/32/0/32", "memory": "131072", "cpu_load": "0.02", "free_mem": "130100", "features": "epyc"},
    {"nodelist": "cpu-node22", "partition": "cpu", "state": "idle", "cpus": "0/32/0/32", "memory": "131072", "cpu_load": "0.00", "free_mem": "130800", "features": "epyc"},
    {"nodelist": "highmem-node01", "partition": "highmem", "state": "idle", "cpus": "0/32/0/32", "memory": "512000", "cpu_load": "0.00", "free_mem": "510200", "features": "epyc,highmem"},
    {"nodelist": "highmem-node02", "partition": "highmem", "state": "allocated", "cpus": "32/0/0/32", "memory": "512000", "cpu_load": "30.50", "free_mem": "198400", "features": "epyc,highmem"},
]


# ---------------------------------------------------------------------------
# Demo app
# ---------------------------------------------------------------------------

class DemoSquidApp(SquidApp):
    """SquidApp with simulated SLURM data."""

    def __init__(self, screenshot_path: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.custom_lists = FAKE_LISTS
        self.notes = dict(FAKE_NOTES)
        self._screenshot_path = screenshot_path

    def refresh_jobs(self) -> None:
        """Override to inject fake data instead of calling SLURM."""
        from squidlib.constants import QUEUE_STATES, RUNNING_STATES
        jobs = [j for j in FAKE_JOBS if j.state in QUEUE_STATES or j.state in RUNNING_STATES]
        completed = []
        history = [j for j in FAKE_JOBS if j.state not in QUEUE_STATES and j.state not in RUNNING_STATES]
        self._apply_jobs(jobs, completed, history, FAKE_PARTITIONS, FAKE_NODES)
        self.sub_title = "Slurm QUeue Interactive Dashboard (user=jinseok) [DEMO]"

        if self._screenshot_path:
            self.set_timer(0.5, self._take_screenshot)

    def _take_screenshot(self) -> None:
        path = Path(self._screenshot_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        svg = self.export_screenshot()

        if path.suffix.lower() == ".svg":
            path.write_text(svg)
        else:
            try:
                import cairosvg
            except ImportError:
                sys.exit(
                    "cairosvg is required for PNG screenshots.\n"
                    "Install it with: pip install cairosvg"
                )
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(path))

        print(f"Screenshot saved to {path}")
        self.exit()


def main():
    parser = argparse.ArgumentParser(description="Squid demo with simulated SLURM data")
    parser.add_argument(
        "--screenshot",
        metavar="PATH",
        help="Save a screenshot and exit (supports .png and .svg)",
    )
    args = parser.parse_args()

    app = DemoSquidApp(screenshot_path=args.screenshot, refresh_interval=300)
    app.run()


if __name__ == "__main__":
    main()
