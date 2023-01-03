"""Fixtures for the Coolmaster integration."""
from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.coolmaster.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_INFO: dict[str, str] = {
    "version": "1",
}

DEFUALT_UNIT_DATA: dict[str, Any] = {
    "is_on": False,
    "thermostat": 20,
    "temperature": 25,
    "fan_speed": "low",
    "mode": "cool",
    "error_code": None,
    "clean_filter": False,
    "swing": None,
    "temperature_unit": "celsius",
}

TEST_UNITS: dict[dict[str, Any]] = {
    "L1.100": {**DEFUALT_UNIT_DATA},
    "L1.101": {
        **DEFUALT_UNIT_DATA,
        **{
            "is_on": True,
            "clean_filter": True,
            "error_code": "Err1",
        },
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

    async def reset_filter(self):
        """Report that the air filter was cleaned and reset the timer."""
        self._attributes["clean_filter"] = False


class CoolMasterNetMock:
    """Mock for CoolMasterNet."""

    def __init__(self, *_args: Any) -> None:
        """Initialize the CoolMasterNetMock."""
        self._data = copy.deepcopy(TEST_UNITS)

    async def info(self) -> dict[str, Any]:
        """Return info about the bridge device."""
        return DEFAULT_INFO

    async def status(self) -> dict[str, CoolMasterNetUnitMock]:
        """Return the units."""
        return {
            key: CoolMasterNetUnitMock(key, attributes)
            for key, attributes in self._data.items()
        }


@pytest.fixture
async def load_int(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Coolmaster integration in Home Assistant."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.3.4",
            "port": 1234,
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
