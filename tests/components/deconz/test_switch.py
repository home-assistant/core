"""deCONZ switch platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "1": {
                "name": "On off switch",
                "type": "On/Off plug-in unit",
                "state": {"on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "name": "Smart plug",
                "type": "Smart plug",
                "state": {"on": False, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "name": "Unsupported switch",
                "type": "Not a switch",
                "state": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
            "4": {
                "name": "On off relay",
                "state": {"on": True, "reachable": True},
                "type": "On/Off light",
                "uniqueid": "00:00:00:00:00:00:00:04-00",
            },
        }
    ],
)
async def test_power_plugs(
    hass: HomeAssistant,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that all supported switch entities are created."""
    assert len(hass.states.async_all()) == 4
    assert hass.states.get("switch.on_off_switch").state == STATE_ON
    assert hass.states.get("switch.smart_plug").state == STATE_OFF
    assert hass.states.get("switch.on_off_relay").state == STATE_ON
    assert hass.states.get("switch.unsupported_switch") is None

    event_changed_light = {
        "r": "lights",
        "id": "1",
        "state": {"on": False},
    }
    await mock_websocket_data(event_changed_light)
    await hass.async_block_till_done()

    assert hass.states.get("switch.on_off_switch").state == STATE_OFF

    # Verify service calls

    aioclient_mock = mock_put_request("/lights/1/state")

    # Service turn on power plug

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.on_off_switch"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True}

    # Service turn off power plug

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.on_off_switch"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"on": False}

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 4
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "1": {
                "name": "On Off output device",
                "type": "On/Off output",
                "state": {"on": True, "reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
        }
    ],
)
async def test_remove_legacy_on_off_output_as_light(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Test that switch platform cleans up legacy light entities."""
    assert entity_registry.async_get_or_create(
        LIGHT_DOMAIN, DECONZ_DOMAIN, "00:00:00:00:00:00:00:00-00"
    )

    await config_entry_factory()

    assert not entity_registry.async_get("light.on_off_output_device")
    assert entity_registry.async_get("switch.on_off_output_device")
    assert len(hass.states.async_all()) == 1
