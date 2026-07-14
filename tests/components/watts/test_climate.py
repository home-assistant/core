"""Tests for the Watts Vision climate platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from visionpluspython.models import ThermostatMode

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.watts.const import (
    ATTR_DURATION,
    DOMAIN,
    SERVICE_ACTIVATE_TIMER_MODE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting temperature."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("climate.living_room_living_room_thermostat")
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == 22.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_TEMPERATURE: 23.5,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_temperature.assert_called_once_with(
        "thermostat_123", 23.5
    )


async def test_fast_polling(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting temperature triggers fast polling that stops."""
    await setup_integration(hass, mock_config_entry)

    # Trigger fast polling
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_TEMPERATURE: 23.5,
        },
        blocking=True,
    )

    mock_watts_client.get_device.reset_mock()

    # Fast polling should be active
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called
    mock_watts_client.get_device.assert_called_with("thermostat_123")

    # Should still be in fast polling after 55s
    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=50))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_watts_client.get_device.called

    mock_watts_client.get_device.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.bedroom_bedroom_thermostat",
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
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.OFF
    )


async def test_set_preset_mode_comfort(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting preset mode to comfort."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_PRESET_MODE: "comfort",
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.COMFORT
    )


async def test_set_preset_mode_defrost(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting preset mode to defrost."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_PRESET_MODE: "defrost",
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.DEFROST
    )


async def test_set_preset_mode_timer(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting preset mode to timer."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_PRESET_MODE: "timer",
        },
        blocking=True,
    )

    mock_watts_client.set_thermostat_mode.assert_called_once_with(
        "thermostat_123", ThermostatMode.TIMER
    )


async def test_set_preset_mode_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting preset mode fails."""
    await setup_integration(hass, mock_config_entry)

    mock_watts_client.set_thermostat_mode.side_effect = RuntimeError("API Error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the preset mode"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
                ATTR_PRESET_MODE: "defrost",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("duration", "expected_minutes"),
    [
        (timedelta(minutes=90), 90),
        (timedelta(minutes=1, seconds=30), 2),
    ],
)
async def test_activate_timer_mode(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    duration: timedelta,
    expected_minutes: int,
) -> None:
    """Test activating timer mode with temperature and duration."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_TIMER_MODE,
        {
            ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
            ATTR_TEMPERATURE: 20.5,
            ATTR_DURATION: duration,
        },
        blocking=True,
    )

    mock_watts_client.activate_thermostat_timer.assert_called_once_with(
        "thermostat_123", 20.5, expected_minutes
    )


@pytest.mark.parametrize("temperature", [4.5, 30.5])
async def test_activate_timer_mode_temperature_out_of_range(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    temperature: float,
) -> None:
    """Test that out-of-range timer temperatures are rejected."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError, match="out of range"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_TIMER_MODE,
            {
                ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
                ATTR_TEMPERATURE: temperature,
                ATTR_DURATION: timedelta(minutes=90),
            },
            blocking=True,
        )

    mock_watts_client.activate_thermostat_timer.assert_not_called()


async def test_activate_timer_mode_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when activating timer mode fails."""
    await setup_integration(hass, mock_config_entry)

    mock_watts_client.activate_thermostat_timer.side_effect = RuntimeError("API Error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while activating timer mode"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_TIMER_MODE,
            {
                ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
                ATTR_TEMPERATURE: 20.5,
                ATTR_DURATION: timedelta(minutes=90),
            },
            blocking=True,
        )


async def test_set_temperature_api_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting temperature fails."""
    await setup_integration(hass, mock_config_entry)

    # Make the API call fail
    mock_watts_client.set_thermostat_temperature.side_effect = RuntimeError("API Error")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the temperature"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
                ATTR_TEMPERATURE: 23.5,
            },
            blocking=True,
        )


async def test_set_hvac_mode_value_error(
    hass: HomeAssistant,
    mock_watts_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test error handling when setting mode fails."""
    await setup_integration(hass, mock_config_entry)

    mock_watts_client.set_thermostat_mode.side_effect = ValueError("Invalid mode")

    with pytest.raises(
        HomeAssistantError, match="An error occurred while setting the HVAC mode"
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.living_room_living_room_thermostat",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )
