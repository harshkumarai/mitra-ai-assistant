"""psutil-based system statistics monitor."""

import time
from typing import TYPE_CHECKING, Any

import psutil

from backend.utils.logger import get_logger

if TYPE_CHECKING:
    from backend.websocket.manager import ConnectionManager

logger = get_logger(__name__)

# Record startup time for uptime calculation
_START_TIME = time.time()


class SystemMonitor:
    """Collects real-time system performance metrics using :pypi:`psutil`.

    All methods are synchronous because psutil itself is synchronous.
    Use :meth:`broadcast_stats` to push stats over WebSocket.
    """

    def get_stats(self) -> dict[str, Any]:
        """Return a snapshot of current system performance metrics.

        Returns:
            Dictionary with keys:
            ``cpu_percent``, ``ram_percent``, ``ram_used_gb``,
            ``ram_total_gb``, ``battery_percent``, ``battery_plugged``,
            ``network_bytes_sent_mb``, ``network_bytes_recv_mb``,
            ``disk_percent``, ``uptime_seconds``.
        """
        # CPU
        cpu_percent: float = psutil.cpu_percent(interval=0.1)

        # RAM
        vm = psutil.virtual_memory()
        ram_percent: float = vm.percent
        ram_used_gb: float = round(vm.used / (1024 ** 3), 2)
        ram_total_gb: float = round(vm.total / (1024 ** 3), 2)

        # Battery
        battery = psutil.sensors_battery()
        battery_percent: float = round(battery.percent, 1) if battery else 0.0
        battery_plugged: bool = battery.power_plugged if battery else False

        # Network (cumulative counters in MB)
        net = psutil.net_io_counters()
        network_bytes_sent_mb: float = round(net.bytes_sent / (1024 ** 2), 2)
        network_bytes_recv_mb: float = round(net.bytes_recv / (1024 ** 2), 2)

        # Disk (root partition)
        disk = psutil.disk_usage("/")
        disk_percent: float = disk.percent

        # Uptime
        uptime_seconds: float = round(time.time() - _START_TIME, 1)

        return {
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "battery_percent": battery_percent,
            "battery_plugged": battery_plugged,
            "network_bytes_sent_mb": network_bytes_sent_mb,
            "network_bytes_recv_mb": network_bytes_recv_mb,
            "disk_percent": disk_percent,
            "uptime_seconds": uptime_seconds,
        }

    def get_top_processes(self, n: int = 10) -> list[dict[str, Any]]:
        """Return the top *n* processes sorted by CPU usage.

        Args:
            n: Number of processes to return (default 10).

        Returns:
            List of dicts with keys: ``name``, ``pid``,
            ``cpu_percent``, ``memory_percent``.
        """
        procs: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["name", "pid", "cpu_percent", "memory_percent"]):
            try:
                info = proc.info  # type: ignore[attr-defined]
                procs.append(
                    {
                        "name": info.get("name", "unknown"),
                        "pid": info.get("pid", 0),
                        "cpu_percent": round(info.get("cpu_percent") or 0.0, 2),
                        "memory_percent": round(info.get("memory_percent") or 0.0, 2),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda p: p["cpu_percent"], reverse=True)
        return procs[:n]

    async def broadcast_stats(self, manager: "ConnectionManager") -> None:
        """Collect system stats and broadcast them to all WebSocket clients.

        Args:
            manager: The :class:`~backend.websocket.manager.ConnectionManager`
                instance to broadcast through.
        """
        import json

        stats = self.get_stats()
        payload = json.dumps({"type": "system_stats", "data": stats})
        await manager.broadcast(payload)
        logger.debug("Broadcast system stats to %d clients.", len(manager.active_connections))


# Module-level singleton
system_monitor = SystemMonitor()
