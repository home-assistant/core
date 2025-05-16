"""Tests for the Dreo fan platform."""

from hscloud.hscloudexception import HsCloudException
import pytest

from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

pytestmark = pytest.mark.usefixtures(
    "mock_dreo_client", "mock_dreo_devices", "mock_fan_device_data", "mock_coordinator"
)


async def test_fan_state(
    hass: HomeAssistant, setup_integration, mock_fan_entity, mock_coordinator
) -> None:
    """Test the creation and state of the fan."""
    await hass.async_block_till_done()

    # Set coordinator data
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True

    # Update entity state
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100
    assert state.attributes[ATTR_PRESET_MODE] == "auto"
    assert state.attributes[ATTR_OSCILLATING] is True


async def test_turn_on(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test turning on the fan."""
    # Turn off the fan first
    mock_coordinator.data.is_on = False
    mock_coordinator.data.mode = None
    mock_coordinator.data.speed_percentage = 0
    mock_coordinator.data.oscillate = None
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state is off
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0

    # Simulate response from the device (successful turn on)
    mock_dreo_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 50,
        "oscillate": False,
    }

    # Update the state
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ["fan.test_fan"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify client was called correctly
    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=True
    )

    # Update coordinator data with the "response" from the API
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = False
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify the state after turning on
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100
    assert state.attributes[ATTR_PRESET_MODE] == "auto"


async def test_turn_off(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test turning off the fan."""
    # Ensure fan is on first
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state is on
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON

    # Simulate response from the device (successful turn off)
    mock_dreo_client.get_status.return_value = {
        "power_switch": False,
        "connected": True,
        "mode": None,
        "speed": 0,
        "oscillate": None,
    }

    # Update the state
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ["fan.test_fan"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify client was called correctly
    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=False
    )

    # Update coordinator data with the "response" from the API
    mock_coordinator.data.is_on = False
    mock_coordinator.data.mode = None
    mock_coordinator.data.speed_percentage = 0
    mock_coordinator.data.oscillate = None
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify the state after turning off
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0


async def test_set_percentage(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the fan speed percentage."""
    # Ensure fan is on with initial settings
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 100

    # Clear any previous calls
    mock_dreo_client.update_status.reset_mock()

    # Simulate response from the device
    mock_dreo_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 2,
        "oscillate": False,
    }

    # Update the state
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PERCENTAGE: 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify client was called correctly
    mock_dreo_client.update_status.assert_called_once_with("test-device-id", speed=2)

    # Update coordinator data with the "response" from the API
    mock_coordinator.data.speed_percentage = 50
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify the state after setting percentage
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 50


async def test_set_preset_mode(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the fan preset mode."""
    # Ensure fan is on with initial settings
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "auto"

    # Clear any previous calls
    mock_dreo_client.update_status.reset_mock()

    # Simulate response from the device
    mock_dreo_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
        "mode": "normal",
        "speed": 50,
        "oscillate": False,
    }

    # Update the state
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_PRESET_MODE: "normal"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify client was called correctly
    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", mode="normal"
    )

    # Update coordinator data with the "response" from the API
    mock_coordinator.data.mode = "normal"
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify the state after setting preset mode
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PRESET_MODE] == "normal"


async def test_set_oscillate(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test setting the fan oscillation."""
    # Ensure fan is on with oscillation enabled
    mock_coordinator.data.is_on = True
    mock_coordinator.data.mode = "auto"
    mock_coordinator.data.speed_percentage = 100
    mock_coordinator.data.oscillate = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.attributes[ATTR_OSCILLATING] is True

    # Clear any previous calls
    mock_dreo_client.update_status.reset_mock()

    # Simulate response from the device
    mock_dreo_client.get_status.return_value = {
        "power_switch": True,
        "connected": True,
        "mode": "auto",
        "speed": 50,
        "oscillate": False,
    }

    # Update the state
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_OSCILLATE,
        {ATTR_ENTITY_ID: ["fan.test_fan"], ATTR_OSCILLATING: False},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify client was called correctly
    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", oscillate=False
    )

    # Update coordinator data with the "response" from the API
    mock_coordinator.data.oscillate = False
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify the state after setting oscillation
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_OSCILLATING] is False


async def test_fan_unavailable(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test handling of an unavailable fan."""
    # Make fan unavailable
    mock_coordinator.data.available = False
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify state is unavailable
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Set back to available and verify state changes
    mock_coordinator.data.available = True
    mock_coordinator.data.is_on = True
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_ON


async def test_client_error(
    hass: HomeAssistant,
    setup_integration,
    mock_dreo_client,
    mock_fan_entity,
    mock_coordinator,
) -> None:
    """Test handling of client errors."""
    # Ensure fan is off initially
    mock_coordinator.data.is_on = False
    mock_coordinator.data.mode = None
    mock_coordinator.data.speed_percentage = 0
    mock_coordinator.data.oscillate = None
    mock_fan_entity.async_write_ha_state()
    await hass.async_block_till_done()

    # Verify initial state
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_OFF

    # Simulate client error
    mock_dreo_client.update_status.side_effect = HsCloudException("Test exception")

    # Attempt to turn on the fan
    with pytest.raises(HsCloudException):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["fan.test_fan"]},
            blocking=True,
        )
    await hass.async_block_till_done()

    # Verify client was called
    mock_dreo_client.update_status.assert_called_once_with(
        "test-device-id", power_switch=True
    )

    # Verify the state remains unchanged after error
    state = hass.states.get("fan.test_fan")
    assert state is not None
    assert state.state == STATE_OFF
