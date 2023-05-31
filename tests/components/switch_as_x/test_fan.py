"""Tests for the Switch as X Fan platform."""
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import (
    CONF_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_default_state(hass: HomeAssistant) -> None:
    """Test fan switch default state."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_TARGET_DOMAIN: Platform.FAN,
        },
        title="Wind Machine",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("fan.wind_machine")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["supported_features"] == 0


async def test_service_calls(hass: HomeAssistant) -> None:
    """Test service calls affecting the switch as fan entity."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.decorative_lights",
            CONF_TARGET_DOMAIN: Platform.FAN,
        },
        title="Title is ignored",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("fan.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TOGGLE,
        {CONF_ENTITY_ID: "fan.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("fan.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "fan.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("fan.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {CONF_ENTITY_ID: "fan.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("fan.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("fan.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("fan.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("fan.decorative_lights").state == STATE_ON
