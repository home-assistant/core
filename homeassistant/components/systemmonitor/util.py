"""Utils for System Monitor."""

import os

import psutil


def get_all_disk_mounts() -> list[str]:
    """Return all disk mount points on system."""
    disks: list[str] = []
    for part in psutil.disk_partitions(all=False):
        if os.name == "nt":
            if "cdrom" in part.opts or part.fstype == "":
                # skip cd-rom drives with no disk in it; they may raise
                # ENOENT, pop-up a Windows GUI error for a non-ready
                # partition or just hang.
                continue
        disks.append(part.mountpoint)
    return disks


def get_all_network_intefaces() -> list[str]:
    """Return all network interfaces on system."""
    interfaces: list[str] = []
    for interface, _ in psutil.net_if_addrs().items():
        interfaces.append(interface)
    return interfaces
