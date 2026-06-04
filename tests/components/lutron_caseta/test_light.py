"""Tests for the Lutron Caseta integration."""

from unittest.mock import patch

from pylutron_caseta.color_value import WarmCoolColorValue

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_light_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)

    ra3_entity_id = "light.basement_bedroom_main_lights"
    caseta_entity_id = "light.kitchen_main_lights"

    # Assert that RA3 lights will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(ra3_entity_id).unique_id == "000004d2_801"

    # Assert that Caseta lights will have the serial number as the uniqueID
    assert entity_registry.async_get(caseta_entity_id).unique_id == "5442321"

    state = hass.states.get(ra3_entity_id)
    assert state.state == STATE_ON


async def test_previous_brightness(
    hass: HomeAssistant,
) -> None:
    """Test brightness tracked and restored."""
    await async_setup_integration(hass, MockBridge)

    caseta_entity_id = "light.kitchen_kitchen_other_lights"

    # 1. Turn on with explicit brightness 25
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 25},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)

    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 25

    # 2. Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)

    # 3. Turn on again without brightness → expect 25
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)

    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) == 25


async def test_previous_brightness_physical_switch(
    hass: HomeAssistant,
) -> None:
    """Test that brightness set via a physical switch is restored on next turn-on."""
    mock_entry = await async_setup_integration(hass, MockBridge)

    caseta_entity_id = "light.kitchen_kitchen_other_lights"
    bridge = mock_entry.runtime_data.bridge

    # Simulate the physical dimmer setting brightness to 72 (Lutron 0-100 scale).
    bridge.devices["902"]["current_state"] = 72
    bridge.call_subscribers("902")
    await hass.async_block_till_done()

    # Turn off via HA.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Turn on via HA without an explicit brightness → expect the physical level.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)
    assert state is not None
    # to_hass_level(72) == (72 * 255) // 100 == 183
    assert state.attributes.get(ATTR_BRIGHTNESS) == 183


async def test_previous_brightness_zero_not_remembered(
    hass: HomeAssistant,
) -> None:
    """Test that a zero brightness is not remembered as the restore level."""
    await async_setup_integration(hass, MockBridge)

    caseta_entity_id = "light.kitchen_kitchen_other_lights"

    # 1. Establish a non-zero previous brightness of 25
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 25},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # 2. Turn on with an explicit brightness of 0 (effectively off)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_BRIGHTNESS: 0},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    # 3. Turn on without brightness → the 0 is ignored and 25 is restored
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {},
        target={ATTR_ENTITY_ID: caseta_entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(caseta_entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 25


class MockBridgeWithColorLight(MockBridge):
    """Mock bridge that also exposes a color-temperature-capable light."""

    def load_devices(self):
        """Add a white-tune light to the standard mock devices."""
        devices = super().load_devices()
        devices["903"] = {
            "device_id": "903",
            "current_state": 50,
            "fan_speed": None,
            "zone": "903",
            "name": "Kitchen_Color Light",
            "button_groups": None,
            "type": "WhiteTune",
            "model": None,
            "serial": 5442323,
            "tilt": None,
            "area": "1025",
            "white_tuning_range": {"Min": 2700, "Max": 6500},
            "color": WarmCoolColorValue(3000),
        }
        return devices


async def test_color_only_turn_on_preserves_brightness(
    hass: HomeAssistant,
) -> None:
    """Test a color-only turn-on does not override the current brightness."""
    mock_entry = await async_setup_integration(hass, MockBridgeWithColorLight)

    entity_id = "light.kitchen_kitchen_color_light"
    bridge = mock_entry.runtime_data.bridge

    with patch.object(bridge, "set_value", wraps=bridge.set_value) as mock_set_value:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_COLOR_TEMP_KELVIN: 3000},
            target={ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

    # A color-only change must leave brightness untouched, i.e. value=None
    assert mock_set_value.call_args is not None
    assert mock_set_value.call_args.kwargs["value"] is None
