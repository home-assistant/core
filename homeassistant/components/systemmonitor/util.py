"""Utils for System Monitor."""

import logging
import os

from psutil._common import shwtemp
import psutil_home_assistant as ha_psutil

from homeassistant.core import HomeAssistant

from .const import CPU_SENSOR_PREFIXES

_LOGGER = logging.getLogger(__name__)

SKIP_DISK_TYPES = {"proc", "tmpfs", "devtmpfs"}


def get_all_disk_mounts(
    hass: HomeAssistant, psutil_wrapper: ha_psutil.PsutilWrapper
) -> set[str]:
    """Return all disk mount points on system."""
    disks: set[str] = set()
    for part in psutil_wrapper.psutil.disk_partitions(all=True):
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
            if not os.path.isdir(part.mountpoint):
                _LOGGER.debug(
                    "Mountpoint %s was excluded because it is not a directory",
                    part.mountpoint,
                )
                continue
            usage = psutil_wrapper.psutil.disk_usage(part.mountpoint)
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


def get_all_network_interfaces(
    hass: HomeAssistant, psutil_wrapper: ha_psutil.PsutilWrapper
) -> set[str]:
    """Return all network interfaces on system."""
    interfaces: set[str] = set()
    for interface in psutil_wrapper.psutil.net_if_addrs():
        if interface.startswith("veth"):
            # Don't load docker virtual network interfaces
            continue
        interfaces.add(interface)
    _LOGGER.debug("Adding interfaces: %s", ", ".join(interfaces))
    return interfaces


def get_all_running_processes(hass: HomeAssistant) -> set[str]:
    """Return all running processes on system."""
    psutil_wrapper = ha_psutil.PsutilWrapper()
    processes: set[str] = set()
    for proc in psutil_wrapper.psutil.process_iter(["name"]):
        if proc.name() not in processes:
            processes.add(proc.name())
    _LOGGER.debug("Running processes: %s", ", ".join(processes))
    return processes


def read_cpu_temperature(temps: dict[str, list[shwtemp]]) -> float | None:
    """Attempt to read CPU / processor temperature."""
    entry: shwtemp

    _LOGGER.debug("CPU Temperatures: %s", temps)
    for name, entries in temps.items():
        for i, entry in enumerate(entries, start=1):
            # In case the label is empty (e.g. on Raspberry PI 4),
            # construct it ourself here based on the sensor key name.
            _label = f"{name} {i}" if not entry.label else entry.label
            # check both name and label because some systems embed cpu# in the
            # name, which makes label not match because label adds cpu# at end.
            if _label in CPU_SENSOR_PREFIXES or name in CPU_SENSOR_PREFIXES:
                return round(entry.current, 1)

    return None
