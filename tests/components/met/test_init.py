"""Test the Met integration init."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.met.const import (
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
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


async def test_removing_incorrect_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    mock_weather: MagicMock,
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


@pytest.mark.parametrize(
    ("title", "expected_title", "entity_id"),
    [
        ("", "Somewhere", "weather.forecast_somewhere"),
        ("Custom title", "Custom title", "weather.forecast_custom_title"),
    ],
)
async def test_migrate_name_to_title(
    hass: HomeAssistant,
    mock_weather: MagicMock,
    title: str,
    expected_title: str,
    entity_id: str,
) -> None:
    """Test legacy stored names migrate to the config entry title when needed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data={
            CONF_NAME: "Somewhere",
            CONF_LATITUDE: 10,
            CONF_LONGITUDE: 20,
            CONF_ELEVATION: 0,
        },
        title=title,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.title == expected_title
    assert entry.data == {
        CONF_LATITUDE: 10,
        CONF_LONGITUDE: 20,
        CONF_ELEVATION: 0,
    }
    assert hass.states.async_entity_ids("weather") == [entity_id]
