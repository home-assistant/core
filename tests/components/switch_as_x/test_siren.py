"""Tests for the Switch as X Siren platform."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN, SirenService
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.components.switch_as_x.config_flow import SwitchAsXConfigFlowHandler
from homeassistant.components.switch_as_x.const import (
    CONF_INVERT,
    CONF_TARGET_DOMAIN,
    DOMAIN,
)
from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON, Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_default_state(hass: HomeAssistant) -> None:
    """Test siren switch default state."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.test",
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: Platform.SIREN,
        },
        title="Noise Maker",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("siren.noise_maker")
    assert state is not None
    assert state.state == "unavailable"
    assert state.attributes["supported_features"] == 3


async def test_service_calls(hass: HomeAssistant) -> None:
    """Test service calls affecting the switch as siren entity."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.decorative_lights",
            CONF_INVERT: False,
            CONF_TARGET_DOMAIN: Platform.SIREN,
        },
        title="Title is ignored",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TOGGLE,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_ON,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_OFF,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TOGGLE,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON


async def test_service_calls_inverted(hass: HomeAssistant) -> None:
    """Test service calls affecting the switch as siren entity."""
    await async_setup_component(hass, "switch", {"switch": [{"platform": "demo"}]})
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_ENTITY_ID: "switch.decorative_lights",
            CONF_INVERT: True,
            CONF_TARGET_DOMAIN: Platform.SIREN,
        },
        title="Title is ignored",
        version=SwitchAsXConfigFlowHandler.VERSION,
        minor_version=SwitchAsXConfigFlowHandler.MINOR_VERSION,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TOGGLE,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_ON,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SIREN_DOMAIN,
        SirenService.TURN_OFF,
        {TargetKey.ENTITY_ID: "siren.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_OFF,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_OFF
    assert hass.states.get("siren.decorative_lights").state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TOGGLE,
        {TargetKey.ENTITY_ID: "switch.decorative_lights"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.decorative_lights").state == STATE_ON
    assert hass.states.get("siren.decorative_lights").state == STATE_ON
