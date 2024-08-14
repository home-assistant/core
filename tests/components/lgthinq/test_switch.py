"""Tests for the thinq switch platform."""

from unittest.mock import patch

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import (
    get_mock_lg_device_for_type,
    mock_device_status,
    mock_thinq_api_response,
)
from .const import DEHUMIDIFIER

from tests.common import MockConfigEntry


async def test_switch(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Test the lgthinq switch."""
    # Check states are exist and attributes are initialized as expected.
    state = hass.states.get("switch.test_dehumidifier_power")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None

    # Get the associated device and update status.
    dehumidifier = get_mock_lg_device_for_type(init_integration, DEHUMIDIFIER)
    assert dehumidifier

    with patch(
        "homeassistant.components.lgthinq.device.LGDevice.async_get_device_status",
        return_value=mock_device_status(DEHUMIDIFIER),
    ):
        await dehumidifier.async_update_status()
        await dehumidifier.coordinator.async_refresh()

    # Check states are updated correctly.
    state = hass.states.get("switch.test_dehumidifier_power")
    assert state
    assert state.state == STATE_ON


async def test_switch_on_off_success(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test turning the switch on and off with success response."""
    # Check states are exist and attributes are initialized as expected.
    state = hass.states.get("switch.test_dehumidifier_power")
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.lgthinq.property.Property._async_post_value",
        return_value=mock_thinq_api_response(status=200, body={}),
    ):
        try:
            # Call turn on service with posting fake status.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.test_dehumidifier_power"},
                blocking=True,
            )
            await hass.async_block_till_done()
        except ServiceValidationError:
            pass

        # Check states are updated correctly.
        state = hass.states.get("switch.test_dehumidifier_power")
        assert state
        assert state.state == STATE_ON

        # Call turn off service with posting fake status.
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_dehumidifier_power"},
            blocking=True,
        )
        await hass.async_block_till_done()

        # Check states are updated correctly.
        state = hass.states.get("switch.test_dehumidifier_power")
        assert state
        assert state.state == STATE_OFF


async def test_switch_on_fail(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test turning the switch on with fail response."""
    # Check states are exist and attributes are initialized as expected.
    state = hass.states.get("switch.test_dehumidifier_power")
    assert state
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.lgthinq.property.Property._async_post_value",
        return_value=mock_thinq_api_response(status=400, body={}),
    ):
        try:
            # Call turn on service with posting fake status.
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: "switch.test_dehumidifier_power"},
                blocking=True,
            )
            await hass.async_block_till_done()
        except ServiceValidationError:
            pass

        # Check state has been rolled back correctly.
        state = hass.states.get("switch.test_dehumidifier_power")
        assert state
        assert state.state == STATE_OFF
