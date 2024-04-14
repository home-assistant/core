"""The tests for mobile_app logbook."""

from homeassistant.components.mobile_app.logbook import (
    DOMAIN,
    IOS_EVENT_ZONE_ENTERED,
    IOS_EVENT_ZONE_EXITED,
)
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_ICON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.logbook.common import MockRow, mock_humanify


async def test_humanify_ios_events(hass: HomeAssistant) -> None:
    """Test humanifying ios events."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    hass.states.async_set(
        "zone.bad_place",
        "0",
        {ATTR_FRIENDLY_NAME: "passport control", ATTR_ICON: "mdi:airplane-marker"},
    )
    await hass.async_block_till_done()

    (event1, event2) = mock_humanify(
        hass,
        [
            MockRow(
                IOS_EVENT_ZONE_ENTERED,
                {"sourceDeviceName": "test_phone", "zone": "zone.happy_place"},
            ),
            MockRow(
                IOS_EVENT_ZONE_EXITED,
                {"sourceDeviceName": "test_phone", "zone": "zone.bad_place"},
            ),
        ],
    )

    assert event1["name"] == "test_phone"
    assert event1["domain"] == DOMAIN
    assert event1["message"] == "entered zone zone.happy_place"
    assert event1["icon"] == "mdi:crosshairs-gps"
    assert event1["entity_id"] == "zone.happy_place"

    assert event2["name"] == "test_phone"
    assert event2["domain"] == DOMAIN
    assert event2["message"] == "exited zone passport control"
    assert event2["icon"] == "mdi:airplane-marker"
    assert event2["entity_id"] == "zone.bad_place"
