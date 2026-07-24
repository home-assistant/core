"""Test the Met integration init."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.met.const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
    HOME_LOCATION_NAME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import device_registry as dr

from . import init_integration

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_fail_default_home_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test abort setup of default home location."""
    await async_process_ha_core_config(
        hass,
        {"latitude": 52.3731339, "longitude": 4.8903147},
    )

    assert hass.config.latitude == DEFAULT_HOME_LATITUDE
    assert hass.config.longitude == DEFAULT_HOME_LONGITUDE

    entry = await init_integration(hass, track_home=True)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.SETUP_ERROR

    assert (
        "Skip setting up met.no integration; No Home location has been set"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("data", "title", "expected_data", "expected_title"),
    [
        pytest.param(
            {
                CONF_NAME: "test",
                CONF_LATITUDE: 0,
                CONF_LONGITUDE: 1.0,
                CONF_ELEVATION: 1.0,
            },
            "Somewhere",
            {CONF_LATITUDE: 0, CONF_LONGITUDE: 1.0, CONF_ELEVATION: 1.0},
            "Somewhere",
            id="name_removed_title_kept",
        ),
        pytest.param(
            {
                CONF_NAME: "test",
                CONF_LATITUDE: 0,
                CONF_LONGITUDE: 1.0,
                CONF_ELEVATION: 1.0,
            },
            "",
            {CONF_LATITUDE: 0, CONF_LONGITUDE: 1.0, CONF_ELEVATION: 1.0},
            "test",
            id="empty_title_replaced_by_name",
        ),
        pytest.param(
            {CONF_TRACK_HOME: True},
            HOME_LOCATION_NAME,
            {CONF_TRACK_HOME: True},
            HOME_LOCATION_NAME,
            id="track_home_without_name",
        ),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    data: dict[str, Any],
    title: str,
    expected_data: dict[str, Any],
    expected_title: str,
) -> None:
    """Test migrating a config entry to the version without a name in data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        title=title,
        minor_version=1,
    )
    with patch(
        "homeassistant.components.met.coordinator.metno.MetWeatherData.fetching_data",
        return_value=True,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data == expected_data
    assert entry.title == expected_title


async def test_migrate_entry_future_version(hass: HomeAssistant) -> None:
    """Test migrating a config entry from the future fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_LATITUDE: 0, CONF_LONGITUDE: 1.0, CONF_ELEVATION: 1.0},
        version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_removing_incorrect_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_weather,
) -> None:
    """Test we remove incorrect devices."""
    entry = await init_integration(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        name="Forecast_legacy",
        entry_type=dr.DeviceEntryType.SERVICE,
        identifiers={(DOMAIN,)},
        manufacturer="Met.no",
        model="Forecast",
        configuration_url="https://www.met.no/en",
    )

    assert await hass.config_entries.async_reload(entry.entry_id)
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert not device_registry.async_get_device(identifiers={(DOMAIN,)})
    assert device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert "Removing improper device Forecast_legacy" in caplog.text
