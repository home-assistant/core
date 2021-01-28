"""The tests for deCONZ logbook."""

from copy import deepcopy

from homeassistant.components import logbook
from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT
from homeassistant.components.deconz.gateway import get_gateway_from_config_entry
from homeassistant.const import CONF_DEVICE_ID, CONF_EVENT, CONF_ID, CONF_UNIQUE_ID
from homeassistant.setup import async_setup_component

from .test_gateway import DECONZ_WEB_REQUEST, setup_deconz_integration

from tests.components.logbook.test_init import MockLazyEventPartialState


async def test_humanifying_deconz_event(hass):
    """Test humanifying deCONZ event."""
    data = deepcopy(DECONZ_WEB_REQUEST)
    data["sensors"] = {
        "0": {
            "id": "Switch 1 id",
            "name": "Switch 1",
            "type": "ZHASwitch",
            "state": {"buttonevent": 1000},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:01-00",
        },
        "1": {
            "id": "Hue remote id",
            "name": "Hue remote",
            "type": "ZHASwitch",
            "modelid": "RWL021",
            "state": {"buttonevent": 1000},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:02-00",
        },
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)

    events = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[0].device_id,
                        CONF_EVENT: 2000,
                        CONF_ID: gateway.events[0].event_id,
                        CONF_UNIQUE_ID: gateway.events[0].serial,
                    },
                ),
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[1].device_id,
                        CONF_EVENT: 2001,
                        CONF_ID: gateway.events[1].event_id,
                        CONF_UNIQUE_ID: gateway.events[1].serial,
                    },
                ),
            ],
            entity_attr_cache,
            {},
        )
    )

    assert events[0]["name"] == "Switch 1"
    assert events[0]["domain"] == "deconz"
    assert events[0]["message"] == "fired event '2000'."

    assert events[1]["name"] == "Hue remote"
    assert events[1]["domain"] == "deconz"
    assert events[1]["message"] == "'Long press' event for 'Dim up' was fired."
