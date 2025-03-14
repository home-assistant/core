"""Tests for the moehlenhoff_alpha2 integration."""

from unittest.mock import patch

import xmltodict

from homeassistant.components.moehlenhoff_alpha2.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture

MOCK_BASE_HOST = "fake-base-host"


async def mock_update_data(self):
    """Mock Alpha2Base.update_data."""
    data = xmltodict.parse(load_fixture("static2.xml", DOMAIN))
    for _type in ("HEATAREA", "HEATCTRL", "IODEVICE"):
        if not isinstance(data["Devices"]["Device"][_type], list):
            data["Devices"]["Device"][_type] = [data["Devices"]["Device"][_type]]
    self.static_data = data


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    with patch(
        "homeassistant.components.moehlenhoff_alpha2.coordinator.Alpha2Base.update_data",
        mock_update_data,
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
