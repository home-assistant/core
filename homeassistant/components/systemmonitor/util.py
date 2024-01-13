"""Utils for System Monitor."""

import logging
import os

import psutil

_LOGGER = logging.getLogger(__name__)

SKIP_DISK_TYPES = {"proc", "tmpfs", "devtmpfs"}


def get_all_disk_mounts() -> set[str]:
    """Return all disk mount points on system."""
    disks: set[str] = set()
    for part in psutil.disk_partitions(all=True):
        if os.name == "nt":
            if "cdrom" in part.opts or part.fstype == "":
                # skip cd-rom drives with no disk in it; they may raise
                # ENOENT, pop-up a Windows GUI error for a non-ready
                # partition or just hang.
                continue
        if part.fstype in SKIP_DISK_TYPES:
            # Ignore disks which are memory
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            _LOGGER.debug(
                "No permission for running user to access %s", part.mountpoint
            )
            continue
        except OSError as err:
            _LOGGER.debug(
                "Mountpoint %s was excluded because of: %s", part.mountpoint, err
            )
            continue
        if usage.total > 0 and part.device != "":
            disks.add(part.mountpoint)
    _LOGGER.debug("Adding disks: %s", ", ".join(disks))
    return disks


def get_all_network_interfaces() -> set[str]:
    """Return all network interfaces on system."""
    interfaces: set[str] = set()
    for interface, _ in psutil.net_if_addrs().items():
        interfaces.add(interface)
    _LOGGER.debug("Adding interfaces: %s", ", ".join(interfaces))
    return interfaces


def get_all_running_processes() -> set[str]:
    """Return all running processes on system."""
    processes: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        if proc.name() not in processes:
            processes.add(proc.name())
    _LOGGER.debug("Running processes: %s", ", ".join(processes))
    return processes
