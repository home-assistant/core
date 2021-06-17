"""Models for TCP platform."""
from __future__ import annotations

from typing import TypedDict

from homeassistant.helpers.template import Template


class TcpSensorConfig(TypedDict):
    """TypedDict for TcpSensor config."""

    name: str
    host: str
    port: str
    timeout: int
    payload: str
    unit_of_measurement: str | None
    value_template: Template | None
    value_on: str | None
    buffer_size: int
    ssl: bool
    verify_ssl: bool
