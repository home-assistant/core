"""Fixtures for the Coolmaster integration."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_INFO: dict[str, str] = {
    "version": "1",
}

TEST_UNITS: dict[dict[str, Any]] = {
    "L1.100": {
        "is_on": False,
        "thermostat": 20,
        "temperature": 25,
        "temperature_unit": "celsius",
        "fan_speed": "low",
        "mode": "cool",
        "error_code": None,
        "clean_filter": False,
        "swing": None,
    },
    "L1.101": {
        "is_on": True,
        "thermostat": 68,
        "temperature": 50,
        "temperature_unit": "imperial",
        "fan_speed": "high",
        "mode": "heat",
        "error_code": "Err1",
        "clean_filter": True,
        "swing": "horizontal",
    },
}


class CoolMasterNetUnitMock:
    """Mock for CoolMasterNetUnit."""

    def __init__(self, unit_id: str, attributes: dict[str, Any]) -> None:
        """Initialize the CoolMasterNetUnitMock."""
        self.unit_id = unit_id
        self._attributes = attributes
        for key, value in attributes.items():
            setattr(self, key, value)

    async def set_fan_speed(self, value: str) -> CoolMasterNetUnitMock:
        """Set the fan speed."""
        self._attributes["fan_speed"] = value
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def set_mode(self, value: str) -> CoolMasterNetUnitMock:
        """Set the mode."""
        self._attributes["mode"] = value
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def set_thermostat(self, value: float) -> CoolMasterNetUnitMock:
        """Set the target temperature."""
        self._attributes["thermostat"] = value
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def set_swing(self, value: str | None) -> CoolMasterNetUnitMock:
        """Set the swing mode."""
        if value == "":
            raise ValueError
        self._attributes["swing"] = value
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def turn_on(self) -> CoolMasterNetUnitMock:
        """Turn a unit on."""
        self._attributes["is_on"] = True
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def turn_off(self) -> CoolMasterNetUnitMock:
        """Turn a unit off."""
        self._attributes["is_on"] = False
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)

    async def reset_filter(self) -> CoolMasterNetUnitMock:
        """Report that the air filter was cleaned and reset the timer."""
        self._attributes["clean_filter"] = False
        return CoolMasterNetUnitMock(self.unit_id, self._attributes)


class CoolMasterNetMock:
    """Mock for CoolMasterNet."""

    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        """Initialize the CoolMasterNetMock."""
        self._units = copy.deepcopy(TEST_UNITS)

    async def info(self) -> dict[str, Any]:
        """Return info about the bridge device."""
        return DEFAULT_INFO

    async def status(self) -> dict[str, CoolMasterNetUnitMock]:
        """Return the units."""
        return {
            unit_id: CoolMasterNetUnitMock(unit_id, attributes)
            for unit_id, attributes in self._units.items()
        }


@pytest.fixture
async def load_int(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Coolmaster integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "port": 1234,
            "supported_modes": [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT],
        },
    )

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.coolmaster.CoolMasterNet",
        new=CoolMasterNetMock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
