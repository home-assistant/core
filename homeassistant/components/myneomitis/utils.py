"""Utility functions for the MyNeomitis integration.

This module provides helper functions to process and format data
for the MyNeomitis integration, such as formatting weekly schedules.
"""

from typing import Any

PRESET_MODE_MAP = {
    "comfort": 1,
    "eco": 2,
    "antifrost": 3,
    "standby": 4,
    "boost": 6,
    "setpoint": 8,
    "comfort_plus": 20,
    "eco_1": 40,
    "eco_2": 41,
    "auto": 60,
}

PRESET_MODE_MAP_RELAIS = {
    "on": 1,
    "off": 2,
    "auto": 60,
}

PRESET_MODE_MAP_UFH = {
    "heating": 0,
    "cooling": 1,
}

REVERSE_PRESET_MODE_MAP = {v: k for k, v in PRESET_MODE_MAP.items()}

REVERSE_PRESET_MODE_MAP_RELAIS = {v: k for k, v in PRESET_MODE_MAP_RELAIS.items()}

REVERSE_PRESET_MODE_MAP_UFH = {v: k for k, v in PRESET_MODE_MAP_UFH.items()}


def seconds_to_hhmm(seconds: int) -> str:
    """Convert seconds to HH:MM format.

    Args:
        seconds (int): The number of seconds to convert.

    Returns:
        str: The time in HH:MM format.

    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02}:{minutes:02}"


def format_week_schedule(
    schedule: dict[str, list[dict[str, Any]]], isRelais: bool = False
) -> dict[str, str]:
    """Format the entire week's schedule for a device, sorted by start time.

    Args:
        schedule (dict[str, list[dict[str, Any]]]): The schedule data with day indices as keys.
        isRelais (bool): Indicates if the device is a RELAIS.

    Returns:
        dict[str, str]: A dictionary where keys are weekday names and values are formatted schedules.

    """
    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    week_schedule = {}

    for i, day_name in enumerate(days):
        blocks = schedule.get(str(i), [])

        # Sort blocks by start time
        blocks.sort(key=lambda block: block["begin"])

        lines = []
        for block in blocks:
            start = seconds_to_hhmm(block["begin"])
            end = seconds_to_hhmm(block["end"])
            val = block.get("value")
            if not isRelais:
                if isinstance(val, int):
                    mode = REVERSE_PRESET_MODE_MAP.get(val, "unknown")
                else:
                    mode = "unknown"
            elif isinstance(val, int):
                mode = REVERSE_PRESET_MODE_MAP_RELAIS.get(val, "unknown")
            else:
                mode = "unknown"
            mode = mode.ljust(10)
            lines.append(f"{start} → {end} : {mode}")

        week_schedule[day_name] = "\n".join(lines) if lines else "No schedule"

    return week_schedule


def parents_to_dict(parents_str: str) -> dict[str, str | None]:
    """Convert a comma-separated string to a dictionary.

    Args:
        parents_str (str): A comma-separated string of parent identifiers.

    Returns:
        dict[str, str | None]: A dictionary with 'gateway' as the first key, and 'primary' as the second key if it exists.

    """
    elements = [el for el in parents_str.split(",") if el]
    result: dict[str, str | None] = {}
    if not elements:
        return result
    result["gateway"] = elements[0]
    if len(elements) > 1:
        result["primary"] = elements[1]
    return result


def get_device_by_rfid(
    devices: list[dict[str, Any]], rfid: str | None
) -> dict[str, Any] | None:
    """Return the device dictionary matching the given RFID.

    Args:
        devices (list[dict[str, Any]]): List of device dictionaries.
        rfid (str): The RFID of the device to search for.

    Returns:
        dict[str, Any] | None: The matching device dictionary, or None if not found.

    """
    for device in devices:
        if device.get("rfid") == rfid:
            return device
    return None


class CtnType:
    """Represents different types of sensors with associated labels and utility methods."""

    NONE = 0
    FLOOR = 1
    FLOW = 2
    OUTSIDE = 3

    LABELS = {
        NONE: "NTC",
        FLOOR: "Floor",
        FLOW: "Flow",
        OUTSIDE: "Outside",
    }

    @staticmethod
    def to_binary(ctn_type: int) -> str:
        """Convert a sensor type to its binary representation.

        Args:
            ctn_type (int): The sensor type to convert.

        Returns:
            str: A binary string representation of the sensor type.

        """
        return format(ctn_type, "02b")

    @staticmethod
    def get_label(ctn_type: int) -> str:
        """Retrieve the label for a given sensor type.

        Args:
            ctn_type (int): The sensor type to retrieve the label for.

        Returns:
            str: The label corresponding to the sensor type, or "NTC" if not found.

        """
        return CtnType.LABELS.get(ctn_type, "NTC")


class Sensors:
    """Represents a collection of sensors with their types."""

    def __init__(
        self,
        ctn0: int = CtnType.NONE,
        ctn1: int = CtnType.NONE,
        ctn2: int = CtnType.NONE,
    ) -> None:
        """Initialize the Sensors instance with sensor types.

        Args:
            ctn0 (int): The type of the first sensor.
            ctn1 (int): The type of the second sensor.
            ctn2 (int): The type of the third sensor.

        """
        self.ctn0 = ctn0
        self.ctn1 = ctn1
        self.ctn2 = ctn2

    @classmethod
    def from_number(cls, ctn_type_number: int) -> "Sensors":
        """Create a Sensors instance from a 6-bit number representing sensor types.

        Args:
            ctn_type_number (int): A 6-bit integer where each pair of bits represents a sensor type.

        Returns:
            Sensors: An instance of the Sensors class with the decoded sensor types.

        """
        bits = format(ctn_type_number, "06b")
        ctn2 = int(bits[0:2], 2)
        ctn1 = int(bits[2:4], 2)
        ctn0 = int(bits[4:6], 2)
        return cls(ctn0=ctn0, ctn1=ctn1, ctn2=ctn2)
