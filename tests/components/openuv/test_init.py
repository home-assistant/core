"""Tests for the OpenUV integration."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.openuv.const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_SENSORS,
)
from homeassistant.core import HomeAssistant

from .conftest import TEST_API_KEY, TEST_ELEVATION, TEST_LATITUDE, TEST_LONGITUDE


@pytest.mark.usefixtures("mock_pyopenuv")
async def test_migrate_entry(hass: HomeAssistant) -> None:
    """Test entry migration."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{TEST_LATITUDE}, {TEST_LONGITUDE}",
        data={
            CONF_BINARY_SENSORS: ["uv_protection_window"],
            CONF_SENSORS: ["safe_exposure_time_type_1"],
            CONF_API_KEY: TEST_API_KEY,
            CONF_LONGITUDE: TEST_LONGITUDE,
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_ELEVATION: TEST_ELEVATION,
        },
        options={CONF_FROM_WINDOW: 3.5, CONF_TO_WINDOW: 3.5},
        version=1,
    )

    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    assert entry.version == 3
    assert entry.data == {
        CONF_API_KEY: TEST_API_KEY,
        CONF_LOCATION: {CONF_LONGITUDE: TEST_LONGITUDE, CONF_LATITUDE: TEST_LATITUDE},
        CONF_ELEVATION: TEST_ELEVATION,
    }
