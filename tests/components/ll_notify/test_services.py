"""Test ll_notify services."""

from async_timeout import timeout
import pytest

from homeassistant.components.ll_notify.const import DOMAIN, FRONTEND_SCRIPT_URL
from homeassistant.exceptions import ServiceNotFound
from homeassistant.setup import async_setup_component

CONFIG = {DOMAIN: {"notifier": {"delay": 5}}}

SERVICES = [
    "success",
    "error",
    "warning",
    "message",
    "notify",
    "alert",
    "confirm",
    "dismiss_all",
    "get_defaults",
    "ping",
    "fire_event",
]


async def test_setup(hass, hass_ws_client):
    """Test setup."""

    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    assert FRONTEND_SCRIPT_URL in hass.data.get("frontend_extra_module_url")
    assert hass.data.get("integrations", {}).get("ll_notify", set())
    assert hass.services.has_service(DOMAIN, "ping")
    assert not hass.services.has_service(DOMAIN, "BOGUS")


async def test_all_services(hass, hass_ws_client):
    """Test all ll_notify services.

    For each ll_notify service:
         hass.call_service()
         await websocket response.
    """
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()

    counter = 10
    wsclient = await hass_ws_client(hass)
    await wsclient.send_json(
        {"id": counter, "type": "subscribe_events", "event_type": "call_service"}
    )

    result = await wsclient.receive_json()
    assert result["id"] == counter
    assert result["type"] == "result"
    assert result["success"]

    counter += 1

    FAKE_DATA = {"data": {"key1": "val1"}}
    for service in SERVICES:
        await hass.services.async_call(DOMAIN, service, FAKE_DATA)
        with timeout(3):
            inbound_msg = await wsclient.receive_json()
        assert inbound_msg["type"] == "event"
        assert inbound_msg["event"]["event_type"] == "call_service"
        assert inbound_msg["event"]["data"]["domain"] == DOMAIN
        assert inbound_msg["event"]["data"]["service"] == service
        assert inbound_msg["event"]["data"]["service_data"] == FAKE_DATA

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(DOMAIN, "BOGUS", FAKE_DATA)
