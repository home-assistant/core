"""Tests for the Watts Vision climate platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from visionpluspython.models import ThermostatMode

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entities."""
    with patch("homeassistant.components.watts.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry, mock_watts_client)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    state = hass.states.get("climate.living_room_thermostat")
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == 22.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_TEMPERATURE: 23.5,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_temperature.assert_called_once_with(
        "thermostat_123", 23.5
    )


async def test_set_temperature_triggers_fast_polling(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that setting temperature triggers fast polling."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    # Trigger fast polling
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_TEMPERATURE: 23.5,
        },
        blocking=True,
    )

    # Reset mock to count only fast polling calls
    mock_watts_client.get_device.reset_mock()

    # Advance time by 5 seconds (fast polling interval)
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called
    mock_watts_client.get_device.assert_called_with("thermostat_123", refresh=True)


async def test_fast_polling_stops_after_duration(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that fast polling stops after the duration expires."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    # Trigger fast polling
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_TEMPERATURE: 23.5,
        },
        blocking=True,
    )

    # Reset mock to count only fast polling calls
    mock_watts_client.get_device.reset_mock()

    # Should be in fast pooling 55s after
    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=55))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called

    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should be called one last time to check if duration expired, then stop

    # Fast polling should be done now
    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_watts_client.get_device.called


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to heat."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.COMFORT
    )


async def test_set_hvac_mode_auto(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to auto."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.bedroom_thermostat",
            ATTR_HVAC_MODE: HVACMode.AUTO,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_456", ThermostatMode.PROGRAM
    )


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting HVAC mode to off."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_thermostat",
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.OFF
    )


async def test_set_temperature_api_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting temperature fails."""
    await setup_integration(hass, mock_config_entry, mock_watts_client)

    # Make the API call fail
    mock_watts_client.set_thermostat_temperature.side_effect = RuntimeError("API Error")

    with pytest.raises(HomeAssistantError, match="Error setting temperature"):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.living_room_thermostat",
                ATTR_TEMPERATURE: 23.5,
            },
            blocking=True,
        )
