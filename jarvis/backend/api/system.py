"""System monitoring API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.monitoring.system_monitor import system_monitor
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stats", summary="Get system performance stats")
async def get_system_stats() -> dict[str, Any]:
    """Return a snapshot of CPU, RAM, battery, network, disk, and uptime.

    Returns:
        Dictionary with keys: ``cpu_percent``, ``ram_percent``,
        ``ram_used_gb``, ``ram_total_gb``, ``battery_percent``,
        ``battery_plugged``, ``network_bytes_sent_mb``,
        ``network_bytes_recv_mb``, ``disk_percent``, ``uptime_seconds``.
    """
    try:
        stats = system_monitor.get_stats()
        logger.debug("System stats retrieved successfully.")
        return stats
    except Exception as exc:
        logger.error("Error retrieving system stats: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve system statistics") from exc


@router.get("/processes", summary="Get top processes by CPU usage")
async def get_top_processes() -> list[dict[str, Any]]:
    """Return the top 10 processes sorted by CPU usage.

    Returns:
        List of dicts with ``name``, ``pid``, ``cpu_percent``,
        ``memory_percent``.
    """
    try:
        processes = system_monitor.get_top_processes(n=10)
        logger.debug("Top processes retrieved successfully.")
        return processes
    except Exception as exc:
        logger.error("Error retrieving top processes: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve process information") from exc
