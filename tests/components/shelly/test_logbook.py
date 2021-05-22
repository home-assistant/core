"""The tests for Shelly logbook."""
from homeassistant.components import logbook
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    EVENT_SHELLY_CLICK,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.setup import async_setup_component

from tests.components.logbook.test_init import MockLazyEventPartialState


async def test_humanify_shelly_click_event(hass, coap_wrapper):
    """Test humanifying Shelly click event."""
    assert coap_wrapper
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    entity_attr_cache = logbook.EntityAttributeCache(hass)

    event1, event2 = list(
        logbook.humanify(
            hass,
            [
                MockLazyEventPartialState(
                    EVENT_SHELLY_CLICK,
                    {
                        ATTR_DEVICE_ID: coap_wrapper.device_id,
                        ATTR_DEVICE: "shellyix3-12345678",
                        ATTR_CLICK_TYPE: "single",
                        ATTR_CHANNEL: 1,
                    },
                ),
                MockLazyEventPartialState(
                    EVENT_SHELLY_CLICK,
                    {
                        ATTR_DEVICE_ID: "no_device_id",
                        ATTR_DEVICE: "shellyswitch25-12345678",
                        ATTR_CLICK_TYPE: "long",
                        ATTR_CHANNEL: 2,
                    },
                ),
            ],
            entity_attr_cache,
            {},
        )
    )

    assert event1["name"] == "Shelly"
    assert event1["domain"] == DOMAIN
    assert (
        event1["message"] == "'single' click event for Test name channel 1 was fired."
    )

    assert event2["name"] == "Shelly"
    assert event2["domain"] == DOMAIN
    assert (
        event2["message"]
        == "'long' click event for shellyswitch25-12345678 channel 2 was fired."
    )
