"""Test the Teslemetry climate platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import InvalidCommand, VehicleOffline

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.teslemetry.coordinator import SYNC_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import METADATA_NOSCOPE, WAKE_UP_ASLEEP, WAKE_UP_ONLINE

from tests.common import async_fire_time_changed


async def test_climate(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the climate entity is correct."""

    entry = await setup_platform(hass, [Platform.CLIMATE])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    entity_id = "climate.test_climate"
    state = hass.states.get(entity_id)

    # Turn On
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT_COOL

    # Set Temp
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 20},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 20

    # Set Preset
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_PRESET_MODE: "keep"},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODE] == "keep"

    # Turn Off
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF


async def test_errors(
    hass: HomeAssistant,
) -> None:
    """Tests service error is handled."""

    await setup_platform(hass, platforms=[Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with (
        patch(
            "homeassistant.components.teslemetry.VehicleSpecific.auto_conditioning_start",
            side_effect=InvalidCommand,
        ) as mock_on,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        mock_on.assert_called_once()
        assert error.from_exception == InvalidCommand


async def test_asleep_or_offline(
    hass: HomeAssistant,
    mock_vehicle_data,
    mock_wake_up,
    mock_vehicle,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests asleep is handled."""

    await setup_platform(hass, [Platform.CLIMATE])
    entity_id = "climate.test_climate"
    mock_vehicle_data.assert_called_once()

    # Put the vehicle alseep
    mock_vehicle_data.reset_mock()
    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(timedelta(seconds=SYNC_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_vehicle_data.assert_called_once()
    mock_wake_up.reset_mock()

    # Run a command but fail trying to wake up the vehicle
    mock_wake_up.side_effect = InvalidCommand
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        assert error
    mock_wake_up.assert_called_once()

    mock_wake_up.side_effect = None
    mock_wake_up.reset_mock()

    # Run a command but timeout trying to wake up the vehicle
    mock_wake_up.return_value = WAKE_UP_ASLEEP
    mock_vehicle.return_value = WAKE_UP_ASLEEP
    with (
        patch("homeassistant.components.teslemetry.entity.asyncio.sleep"),
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: [entity_id]},
            blocking=True,
        )
        assert error
    mock_wake_up.assert_called_once()
    mock_vehicle.assert_called()

    mock_wake_up.reset_mock()
    mock_vehicle.reset_mock()
    mock_wake_up.return_value = WAKE_UP_ONLINE
    mock_vehicle.return_value = WAKE_UP_ONLINE

    # Run a command and wake up the vehicle immediately
    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: [entity_id]}, blocking=True
    )
    await hass.async_block_till_done()
    mock_wake_up.assert_called_once()


async def test_climate_noscope(
    hass: HomeAssistant,
    mock_metadata,
) -> None:
    """Tests that the climate entity is correct."""
    mock_metadata.return_value = METADATA_NOSCOPE

    await setup_platform(hass, [Platform.CLIMATE])
    entity_id = "climate.test_climate"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: [entity_id], ATTR_TEMPERATURE: 20},
            blocking=True,
        )
