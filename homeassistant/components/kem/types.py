"""Support for Oncue types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KemSensor:
    """Kem Sensor."""

    name: str
    display_name: str
    value: str
    display_value: str
    unit: str | None


@dataclass
class KemDevice:
    """Kem Device."""

    name: str
    state: str
    product_name: str
    hardware_version: str
    serial_number: str
    sensors: dict[str, KemSensor]
