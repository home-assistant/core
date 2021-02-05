"""The tests for deCONZ logbook."""

from copy import deepcopy

from homeassistant.components import logbook
from homeassistant.components.deconz.const import CONF_GESTURE
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
        "2": {
            "id": "Xiaomi cube id",
            "name": "Xiaomi cube",
            "type": "ZHASwitch",
            "modelid": "lumi.sensor_cube",
            "state": {"buttonevent": 1000, "gesture": 1},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:03-00",
        },
        "3": {
            "id": "faulty",
            "name": "Faulty event",
            "type": "ZHASwitch",
            "state": {},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:04-00",
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
                # Event without matching device trigger
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[0].device_id,
                        CONF_EVENT: 2000,
                        CONF_ID: gateway.events[0].event_id,
                        CONF_UNIQUE_ID: gateway.events[0].serial,
                    },
                ),
                # Event with matching device trigger
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[1].device_id,
                        CONF_EVENT: 2001,
                        CONF_ID: gateway.events[1].event_id,
                        CONF_UNIQUE_ID: gateway.events[1].serial,
                    },
                ),
                # Gesture with matching device trigger
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[2].device_id,
                        CONF_GESTURE: 1,
                        CONF_ID: gateway.events[2].event_id,
                        CONF_UNIQUE_ID: gateway.events[2].serial,
                    },
                ),
                # Unsupported device trigger
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[2].device_id,
                        CONF_GESTURE: "unsupported_gesture",
                        CONF_ID: gateway.events[2].event_id,
                        CONF_UNIQUE_ID: gateway.events[2].serial,
                    },
                ),
                # Unknown event
                MockLazyEventPartialState(
                    CONF_DECONZ_EVENT,
                    {
                        CONF_DEVICE_ID: gateway.events[3].device_id,
                        "unknown_event": None,
                        CONF_ID: gateway.events[3].event_id,
                        CONF_UNIQUE_ID: gateway.events[3].serial,
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

    assert events[2]["name"] == "Xiaomi cube"
    assert events[2]["domain"] == "deconz"
    assert events[2]["message"] == "fired event 'Shake'."

    assert events[3]["name"] == "Xiaomi cube"
    assert events[3]["domain"] == "deconz"
    assert events[3]["message"] == "fired event 'unsupported_gesture'."

    assert events[4]["name"] == "Faulty event"
    assert events[4]["domain"] == "deconz"
    assert events[4]["message"] == "fired an unknown event."
