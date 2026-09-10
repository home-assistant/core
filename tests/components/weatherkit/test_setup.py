"""Test the WeatherKit setup process."""

from unittest.mock import patch

from apple_weatherkit.client import (
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientError,
)

from homeassistant.components.weatherkit.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import EXAMPLE_CONFIG_DATA, mock_weather_response

from tests.common import MockConfigEntry


async def test_auth_error_handling(hass: HomeAssistant) -> None:
    """Test that we handle authentication errors at setup properly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data=EXAMPLE_CONFIG_DATA,
    )

    with (
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
            side_effect=WeatherKitApiClientAuthenticationError,
        ),
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
            side_effect=WeatherKitApiClientAuthenticationError,
        ),
    ):
        entry.add_to_hass(hass)
        setup_result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert setup_result is False


async def test_client_error_handling(hass: HomeAssistant) -> None:
    """Test that we handle API client errors at setup properly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data=EXAMPLE_CONFIG_DATA,
    )

    with (
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_weather_data",
            side_effect=WeatherKitApiClientError,
        ),
        patch(
            "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
            side_effect=WeatherKitApiClientError,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migration_from_version_1(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities and the device are migrated off their lat/lon-based unique ids."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        data=EXAMPLE_CONFIG_DATA,
        version=1,
    )
    entry.add_to_hass(hass)

    old_unique_id = (
        f"{EXAMPLE_CONFIG_DATA[CONF_LATITUDE]}-{EXAMPLE_CONFIG_DATA[CONF_LONGITUDE]}"
    )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, old_unique_id)},
    )
    weather_entity = entity_registry.async_get_or_create(
        Platform.WEATHER,
        DOMAIN,
        old_unique_id,
        config_entry=entry,
        device_id=device.id,
    )
    sensor_entity = entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{old_unique_id}_pressureTrend",
        config_entry=entry,
        device_id=device.id,
    )

    with mock_weather_response():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, entry.entry_id)}

    assert (
        entity_registry.async_get(weather_entity.entity_id).unique_id == entry.entry_id
    )
    assert (
        entity_registry.async_get(sensor_entity.entity_id).unique_id
        == f"{entry.entry_id}_pressureTrend"
    )
