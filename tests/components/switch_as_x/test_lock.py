"""Tests for the Switch as X Lock platform."""
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switch_as_x.const import CONF_TARGET_DOMAIN, DOMAIN
from homeassistant.const import (
    CONF_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_UNLOCKED,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_default_state(hass: HomeAssistant) -> None:
    """Test lock switch default state."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_TARGET_DOMAIN: Platform.LOCK,
        },
        title="candy_jar",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.candy_jar")
    assert state is not None
    assert state.state == "unavailable"


async def test_service_calls(hass: HomeAssistant) -> None:
    """Test service calls affecting the switch as lock entity."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.decorative_lights",
            CONF_TARGET_DOMAIN: Platform.LOCK,
        },
        title="Title is ignored",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("lock.decorative_lights").state == STATE_UNLOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {CONF_ENTITY_ID: "lock.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("lock.decorative_lights").state == STATE_LOCKED

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {CONF_ENTITY_ID: "lock.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("lock.decorative_lights").state == STATE_UNLOCKED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("lock.decorative_lights").state == STATE_LOCKED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("lock.decorative_lights").state == STATE_UNLOCKED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {CONF_ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("lock.decorative_lights").state == STATE_LOCKED
