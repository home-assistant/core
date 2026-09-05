"""Test Météo France init."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.meteo_france.const import (
    CONF_CITY,
    DEPARTMENTS_WITH_ALERT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.meteo_france.PLATFORMS", []):
        yield


def _second_city(hass: HomeAssistant) -> MockConfigEntry:
    """Return a second entry for a different city in the same department."""
    entry_data = {
        CONF_CITY: "Le Grand-Bornand",
        CONF_LATITUDE: 45.94179,
        CONF_LONGITUDE: 6.42794,
    }
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        unique_id=f"{entry_data[CONF_LATITUDE], entry_data[CONF_LONGITUDE]}",
        title=entry_data[CONF_CITY],
        data=entry_data,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_only_one_city_per_department_provides_alerts(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test the second city in a department does not also provide alerts."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.runtime_data.alert_coordinator is not None

    second_entry = _second_city(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.LOADED
    assert second_entry.runtime_data.alert_coordinator is None


async def test_unload_releases_the_department(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test unloading releases the department so another city can claim it."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.data[DEPARTMENTS_WITH_ALERT]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # The last entry is gone, so the shared registry is cleaned up entirely.
    assert DEPARTMENTS_WITH_ALERT not in hass.data

    second_entry = _second_city(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.runtime_data.alert_coordinator is not None
