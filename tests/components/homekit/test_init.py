"""Test HomeKit initialization."""
from asynctest import patch

from homeassistant import core as ha
from homeassistant.components import logbook
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME,
    ATTR_VALUE,
    DOMAIN as DOMAIN_HOMEKIT,
    EVENT_HOMEKIT_CHANGED,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE
from homeassistant.setup import async_setup_component


async def test_humanify_homekit_changed_event(hass, hk_driver):
    """Test humanifying HomeKit changed event."""
    with patch("homeassistant.components.homekit.HomeKit"):
        assert await async_setup_component(hass, "homekit", {"homekit": {}})

    event1, event2 = list(
        logbook.humanify(
            hass,
            [
                ha.Event(
                    EVENT_HOMEKIT_CHANGED,
                    {
                        ATTR_ENTITY_ID: "lock.front_door",
                        ATTR_DISPLAY_NAME: "Front Door",
                        ATTR_SERVICE: "lock",
                    },
                ),
                ha.Event(
                    EVENT_HOMEKIT_CHANGED,
                    {
                        ATTR_ENTITY_ID: "cover.window",
                        ATTR_DISPLAY_NAME: "Window",
                        ATTR_SERVICE: "set_cover_position",
                        ATTR_VALUE: 75,
                    },
                ),
            ],
        )
    )

    assert event1["name"] == "HomeKit"
    assert event1["domain"] == DOMAIN_HOMEKIT
    assert event1["message"] == "send command lock for Front Door"
    assert event1["entity_id"] == "lock.front_door"

    assert event2["name"] == "HomeKit"
    assert event2["domain"] == DOMAIN_HOMEKIT
    assert event2["message"] == "send command set_cover_position to 75 for Window"
    assert event2["entity_id"] == "cover.window"
