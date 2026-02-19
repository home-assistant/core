"""Utils for System Monitor."""

import logging
import os
import re
from typing import Any

from psutil._common import sfan, shwtemp
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


def read_fan_speed(fans: dict[str, list[sfan]]) -> dict[str, int]:
    """Attempt to read fan speed."""
    entry: sfan

    _LOGGER.debug("Fan speed: %s", fans)
    if not fans:
        return {}
    sensor_fans: dict[str, int] = {}
    for name, entries in fans.items():
        for entry in entries:
            _label = name if not entry.label else entry.label
            sensor_fans[_label] = round(entry.current, 0)

    return sensor_fans


def parse_pressure_file(file_path: str) -> dict[str, dict[str, float | int]] | None:
    """Parses a single /proc/pressure file (cpu, memory, or io).

    Args:
        file_path (str): The full path to the pressure file.

    Returns:
        dict: A dictionary containing the parsed pressure stall information,
              or None if the file cannot be read or parsed.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    data: dict[str, dict[str, float | int]] = {}
    # The regex looks for 'some' and 'full' lines and captures the values.
    # It accounts for floating point numbers and integer values.
    # Example line: "some avg10=0.00 avg60=0.00 avg300=0.00 total=0"
    pattern = re.compile(r"(some|full)\s+(.*)")
    lines = content.strip().split("\n")

    for line in lines:
        match = pattern.match(line)
        if match:
            line_type, values_str = match.groups()
            values: dict[str, float | int] = {}
            for item in values_str.split():
                try:
                    key, value = item.split("=")
                    # Convert values to float, except for 'total' which is an integer
                    if key == "total":
                        values[key] = int(value)
                    else:
                        values[key] = float(value)
                except ValueError:
                    continue
            data[line_type] = values

    return data


def get_all_pressure_info() -> dict[str, Any]:
    """Parses all available pressure information from /proc/pressure/.

    Returns:
        dict: A dictionary containing cpu, memory, and io pressure info.
              Returns an empty dictionary if no pressure files are found.
    """
    pressure_info: dict[str, Any] = {}
    resources = ["cpu", "memory", "io"]

    for resource in resources:
        file_path = f"/proc/pressure/{resource}"
        parsed_data = parse_pressure_file(file_path)
        if parsed_data:
            pressure_info[resource] = parsed_data

    return pressure_info
