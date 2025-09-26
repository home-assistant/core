"""Tests for the Wemo fan entity."""

import pytest
from pywemo.exceptions import ActionException
from pywemo.ouimeaux_device.humidifier import DesiredHumidity, FanMode

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.wemo import fan
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import entity_test_helpers
from .conftest import async_create_wemo_entity


@pytest.fixture
def pywemo_model():
    """Pywemo Humidifier models use the fan platform."""
    return "Humidifier"


# Tests that are in common among wemo platforms. These test methods will be run
# in the scope of this test module. They will run using the pywemo_model from
# this test module (Humidifier).
test_async_update_locked_multiple_updates = (
    entity_test_helpers.test_async_update_locked_multiple_updates
)
test_async_update_locked_multiple_callbacks = (
    entity_test_helpers.test_async_update_locked_multiple_callbacks
)
test_async_update_locked_callback_and_update = (
    entity_test_helpers.test_async_update_locked_callback_and_update
)


async def test_fan_registry_state_callback(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the fan receives state updates from the registry."""
    # On state.
    pywemo_device.get_state.return_value = 1
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_fan_update_entity(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Verify that the fan performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    pywemo_device.get_state.return_value = 1
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    pywemo_device.get_state.return_value = 0
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


async def test_available_after_update(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity
) -> None:
    """Test the availability when an On call fails and after an update."""
    pywemo_device.set_state.side_effect = ActionException
    pywemo_device.get_state.return_value = 1
    await entity_test_helpers.test_avaliable_after_update(
        hass, pywemo_registry, pywemo_device, wemo_entity, FAN_DOMAIN
    )


async def test_turn_off_state(hass: HomeAssistant, wemo_entity) -> None:
    """Test that the device state is updated after turning off."""
    await entity_test_helpers.test_turn_off_state(hass, wemo_entity, FAN_DOMAIN)


async def test_fan_reset_filter_service(
    hass: HomeAssistant, pywemo_device, wemo_entity
) -> None:
    """Verify that SERVICE_RESET_FILTER_LIFE is registered and works."""
    await hass.services.async_call(
        DOMAIN,
        fan.SERVICE_RESET_FILTER_LIFE,
        {ATTR_ENTITY_ID: wemo_entity.entity_id},
        blocking=True,
    )
    pywemo_device.reset_filter_life.assert_called_with()


@pytest.mark.parametrize(
    ("test_input", "expected"),
    [
        (0, DesiredHumidity.FortyFivePercent),
        (45, DesiredHumidity.FortyFivePercent),
        (50, DesiredHumidity.FiftyPercent),
        (55, DesiredHumidity.FiftyFivePercent),
        (60, DesiredHumidity.SixtyPercent),
        (100, DesiredHumidity.OneHundredPercent),
    ],
)
async def test_fan_set_humidity_service(
    hass: HomeAssistant, pywemo_device, wemo_entity, test_input, expected
) -> None:
    """Verify that SERVICE_SET_HUMIDITY is registered and works."""
    await hass.services.async_call(
        DOMAIN,
        fan.SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: wemo_entity.entity_id,
            fan.ATTR_TARGET_HUMIDITY: test_input,
        },
        blocking=True,
    )
    pywemo_device.set_humidity.assert_called_with(expected)


@pytest.mark.parametrize(
    ("percentage", "expected_fan_mode"),
    [
        (0, FanMode.Off),
        (10, FanMode.Minimum),
        (30, FanMode.Low),
        (50, FanMode.Medium),
        (70, FanMode.High),
        (100, FanMode.Maximum),
    ],
)
async def test_fan_set_percentage(
    hass: HomeAssistant, pywemo_device, wemo_entity, percentage, expected_fan_mode
) -> None:
    """Verify set_percentage works properly through the entire range of FanModes."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id], ATTR_PERCENTAGE: percentage},
        blocking=True,
    )
    pywemo_device.set_state.assert_called_with(expected_fan_mode)


async def test_fan_mode_high_initially(hass: HomeAssistant, pywemo_device) -> None:
    """Verify the FanMode is set to High when turned on."""
    pywemo_device.fan_mode = FanMode.Off
    wemo_entity = await async_create_wemo_entity(hass, pywemo_device, "")
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    pywemo_device.set_state.assert_called_with(FanMode.High)
