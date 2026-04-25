"""Fixtures for Daikin tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import urllib.parse

import pytest

type ZoneDefinition = list[str | int]
type ZoneDevice = MagicMock


def _decode_zone_values(value: str) -> list[str]:
    """Decode a semicolon separated list into zone values."""
    return re.findall(r"[^;]+", urllib.parse.unquote(value))


def configure_zone_device(
    zone_device: ZoneDevice,
    *,
    zones: list[ZoneDefinition],
    target_temperature: float | None = 22,
    mode: str = "hot",
    heating_values: str | None = None,
    cooling_values: str | None = None,
) -> None:
    """Configure a mocked zone-capable Daikin device for a test."""
    zone_device.target_temperature = target_temperature
    zone_device.zones = zones
    zone_device._mode = mode

    encoded_zone_temperatures = ";".join(str(zone[2]) for zone in zones)
    zone_device.values = {
        "name": "Daikin Test",
        "model": "TESTMODEL",
        "ver": "1_0_0",
        "zone_name": ";".join(str(zone[0]) for zone in zones),
        "zone_onoff": ";".join(str(zone[1]) for zone in zones),
        "lztemp_h": (
            encoded_zone_temperatures if heating_values is None else heating_values
        ),
        "lztemp_c": (
            encoded_zone_temperatures if cooling_values is None else cooling_values
        ),
    }


@pytest.fixture
def zone_device() -> Generator[ZoneDevice]:
    """Return a mocked zone-capable Daikin device and patch its factory."""
    device = MagicMock(name="DaikinZoneDevice")
    device.mac = "001122334455"
    device.fan_rate = []
    device.swing_modes = []
    device.support_away_mode = False
    device.support_advanced_modes = False
    device.support_fan_rate = False
    device.support_swing_mode = False
    device.support_outside_temperature = False
    device.support_energy_consumption = False
    device.support_humidity = False
    device.support_compressor_frequency = False
    device.compressor_frequency = 0
    device.inside_temperature = 21.0
    device.outside_temperature = 13.0
    device.humidity = 40
    device.current_total_power_consumption = 0.0
    device.last_hour_cool_energy_consumption = 0.0
    device.last_hour_heat_energy_consumption = 0.0
    device.today_energy_consumption = 0.0
    device.today_total_energy_consumption = 0.0

    configure_zone_device(device, zones=[["Living", "1", 22]])

    def _represent(key: str) -> tuple[None, list[str] | str]:
        dynamic_values: dict[str, Callable[[], list[str] | str]] = {
            "lztemp_h": lambda: _decode_zone_values(device.values["lztemp_h"]),
            "lztemp_c": lambda: _decode_zone_values(device.values["lztemp_c"]),
            "mode": lambda: device._mode,
            "f_rate": lambda: "auto",
            "f_dir": lambda: "3d",
            "en_hol": lambda: "off",
            "adv": lambda: "",
            "htemp": lambda: str(device.inside_temperature),
            "otemp": lambda: str(device.outside_temperature),
        }
        return (None, dynamic_values.get(key, lambda: "")())

    async def _set(values: dict[str, Any]) -> None:
        if mode := values.get("mode"):
            device._mode = mode

    device.represent = MagicMock(side_effect=_represent)
    device.update_status = AsyncMock()
    device.set = AsyncMock(side_effect=_set)
    device.set_zone = AsyncMock()
    device.set_holiday = AsyncMock()
    device.set_advanced_mode = AsyncMock()
    device.set_streamer = AsyncMock()

    with patch(
        "homeassistant.components.daikin.DaikinFactory",
        new=AsyncMock(return_value=device),
    ):
        yield device
