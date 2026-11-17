"""System monitoring utility for process memory (VmRSS) and normalized CPU utilization."""

from __future__ import annotations

import os
import time
from typing import Dict


class SystemMonitor:
    """Monitors process-specific CPU & memory (VmRSS) consumption and host total RAM."""

    def __init__(self) -> None:
        self._last_proc_cpu_ticks: float = 0.0
        self._last_proc_time: float = time.time()
        self._proc_cpu_pct: float = 0.0
        self._clk_tck: int = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        self._num_cpus: int = os.cpu_count() or 1
        self._host_total_ram_gb: float = self._get_host_total_ram_gb()
        self._get_proc_cpu()

    def _get_host_total_ram_gb(self) -> float:
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = float(line.split()[1])
                        return round(kb / (1024.0 * 1024.0), 1)
        except Exception:
            pass
        return 16.0

    def _get_proc_cpu(self) -> float:
        try:
            now = time.time()
            dt = now - self._last_proc_time
            with open("/proc/self/stat", "r", encoding="utf-8") as f:
                fields = f.read().split()
            utime = float(fields[13])
            stime = float(fields[14])
            total_ticks = utime + stime
            if self._last_proc_cpu_ticks > 0 and dt > 0:
                d_ticks = total_ticks - self._last_proc_cpu_ticks
                pct = (d_ticks / self._clk_tck / dt / self._num_cpus) * 100.0
                self._proc_cpu_pct = round(min(100.0, max(0.0, pct)), 1)
            self._last_proc_cpu_ticks = total_ticks
            self._last_proc_time = now
        except Exception:
            pass
        return self._proc_cpu_pct

    def _get_proc_ram_mb(self) -> float:
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        kb = float(line.split()[1])
                        return round(kb / 1024.0, 1)
        except Exception:
            pass

        try:
            with open("/sys/fs/cgroup/memory.current", "r", encoding="utf-8") as f:
                b = float(f.read().strip())
                return round(b / (1024.0 * 1024.0), 1)
        except Exception:
            pass

        return 0.0

    def get_metrics(self) -> Dict[str, float]:
        cpu_pct = self._get_proc_cpu()
        app_ram_mb = self._get_proc_ram_mb()
        host_ram_gb = self._host_total_ram_gb

        return {
            "cpu_percent": cpu_pct,
            "app_ram_mb": round(app_ram_mb, 1),
            "host_ram_gb": host_ram_gb,
        }
