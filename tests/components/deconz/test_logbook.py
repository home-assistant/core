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
        }
    }
    config_entry = await setup_deconz_integration(hass, get_state_response=data)
    gateway = get_gateway_from_config_entry(hass, config_entry)
    event = gateway.events[0]

    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)

    event1 = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: event.device_id,
                        CONF_EVENT: 2000,
                        CONF_ID: event.event_id,
                        CONF_UNIQUE_ID: event.serial,
                    },
                ),
            ],
            entity_attr_cache,
            {},
        )
    )[0]

    assert event1["name"] == "Switch 1"
    assert event1["domain"] == "deconz"
    assert event1["message"] == "fired event '2000'."
