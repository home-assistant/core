"""Utils for System Monitor."""

import logging
import os

import psutil

_LOGGER = logging.getLogger(__name__)


def get_all_disk_mounts() -> list[str]:
    """Return all disk mount points on system."""
    disks: list[str] = []
    for part in psutil.disk_partitions(all=True):
        if os.name == "nt":
            if "cdrom" in part.opts or part.fstype == "":
                # skip cd-rom drives with no disk in it; they may raise
                # ENOENT, pop-up a Windows GUI error for a non-ready
                # partition or just hang.
                continue
        usage = psutil.disk_usage(part.mountpoint)
        if usage.total > 0 and part.device != "":
            disks.append(part.mountpoint)
    _LOGGER.debug("Adding disks: %s", ", ".join(disks))
    return disks


def get_all_network_interfaces() -> list[str]:
    """Return all network interfaces on system."""
    interfaces: list[str] = []
    for interface, _ in psutil.net_if_addrs().items():
        interfaces.append(interface)
    _LOGGER.debug("Adding interfaces: %s", ", ".join(interfaces))
    return interfaces


def get_all_running_processes() -> list[str]:
    """Return all running processes on system."""
    processes: list[str] = []
    for proc in psutil.process_iter(["name"]):
        if proc.name() not in processes:
            processes.append(proc.name())
    _LOGGER.debug("Running processes: %s", ", ".join(processes))
    return processes
