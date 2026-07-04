"""Tests for the moehlenhoff_alpha2 integration."""

from functools import partialmethod
from unittest.mock import patch

from moehlenhoff_alpha2 import Alpha2Base
import xmltodict

from homeassistant.components.moehlenhoff_alpha2.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture

MOCK_BASE_HOST = "fake-base-host"


async def mock_update_data(self: Alpha2Base, hass: HomeAssistant) -> None:
    """Mock Alpha2Base.update_data."""
    data = xmltodict.parse(await async_load_fixture(hass, "static2.xml", DOMAIN))
    for _type in ("HEATAREA", "HEATCTRL", "IODEVICE"):
        if not isinstance(data["Devices"]["Device"][_type], list):
            data["Devices"]["Device"][_type] = [data["Devices"]["Device"][_type]]
    self._static_data = data


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_data",
        partialmethod(mock_update_data, hass),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: MOCK_BASE_HOST,
            },
            entry_id="6fa019921cf8e7a3f57a3c2ed001a10d",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry
