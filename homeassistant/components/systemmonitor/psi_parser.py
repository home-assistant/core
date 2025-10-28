"""Parses Pressure Stall Information (PSI) from /proc/pressure files on Linux systems."""

import re
from typing import Any


def parse_pressure_file(file_path: str) -> dict[str, dict[str, float | int]] | None:
    """Parses a single /proc/pressure file (cpu, memory, or io).

    Args:
        file_path (str): The full path to the pressure file.

    Returns:
        dict: A dictionary containing the parsed pressure stall information,
              or None if the file cannot be read or parsed.
    """
    try:
        with open(file_path) as f:
            content = f.read()
    except FileNotFoundError:
        return None
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
                key, value = item.split("=")
                # Convert values to float, except for 'total' which is an integer
                if key == "total":
                    values[key] = int(value)
                else:
                    values[key] = float(value)
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
