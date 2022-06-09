"""The tests for the Traccar device tracker platform."""
from datetime import datetime
from unittest.mock import AsyncMock, patch

from homeassistant.components.device_tracker.const import DOMAIN
from homeassistant.components.traccar.device_tracker import (
    PLATFORM_SCHEMA as TRACCAR_PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_EVENT,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PLATFORM,
    CONF_USERNAME,
)
from homeassistant.setup import async_setup_component

from tests.common import async_capture_events


async def test_import_events_catch_all(hass):
    """Test importing all events and firing them in HA using their event types."""
    conf_dict = {
        DOMAIN: TRACCAR_PLATFORM_SCHEMA(
            {
                CONF_PLATFORM: "traccar",
                CONF_HOST: "fake_host",
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
                CONF_EVENT: ["all_events"],
            }
        )
    }

    device = {"id": 1, "name": "abc123"}
    api_mock = AsyncMock()
    api_mock.devices = [device]
    api_mock.get_events.return_value = [
        {
            "deviceId": device["id"],
            "type": "ignitionOn",
            "serverTime": datetime.utcnow(),
            "attributes": {},
        },
        {
            "deviceId": device["id"],
            "type": "ignitionOff",
            "serverTime": datetime.utcnow(),
            "attributes": {},
        },
    ]

    events_ignition_on = async_capture_events(hass, "traccar_ignition_on")
    events_ignition_off = async_capture_events(hass, "traccar_ignition_off")

    with patch(
        "homeassistant.components.traccar.device_tracker.API", return_value=api_mock
    ):
        assert await async_setup_component(hass, DOMAIN, conf_dict)

    assert len(events_ignition_on) == 1
    assert len(events_ignition_off) == 1
