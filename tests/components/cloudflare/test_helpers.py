"""Test Cloudflare integration helpers."""

from homeassistant.components.cloudflare.helpers import (
    async_create_a_record,
    async_update_proxied_state,
    get_zone_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.test_util.aiohttp import AiohttpClientMocker


def test_get_zone_id() -> None:
    """Test get_zone_id."""
    zones = [
        {"id": "1", "name": "example.com"},
        {"id": "2", "name": "example.org"},
    ]
    assert get_zone_id("example.com", zones) == "1"
    assert get_zone_id("example.org", zones) == "2"
    assert get_zone_id("example.net", zones) is None


async def test_async_create_a_record(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test async_create_a_record."""
    session = async_get_clientsession(hass)

    aioclient_mock.post(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records",
        json={"success": True, "result": {"id": "123"}},
    )
    result = await async_create_a_record(
        session, "token", "zone-id", "test.com", "1.2.3.4", True
    )
    assert result == {"id": "123"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records",
        status=400,
        text="error",
    )
    result = await async_create_a_record(
        session, "token", "zone-id", "test.com", "1.2.3.4", True
    )
    assert result is None

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records",
        json={"success": False, "errors": [{"message": "fail"}]},
    )
    result = await async_create_a_record(
        session, "token", "zone-id", "test.com", "1.2.3.4", True
    )
    assert result is None


async def test_async_update_proxied_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test async_update_proxied_state."""
    session = async_get_clientsession(hass)

    aioclient_mock.put(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/rec-id",
        json={"success": True, "result": {"id": "rec-id"}},
    )
    result = await async_update_proxied_state(
        session, "token", "zone-id", "rec-id", "test.com", "1.2.3.4", True, ttl=1
    )
    assert result is True

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/rec-id",
        status=400,
        text="error",
    )
    result = await async_update_proxied_state(
        session, "token", "zone-id", "rec-id", "test.com", "1.2.3.4", True
    )
    assert result is False

    aioclient_mock.clear_requests()
    aioclient_mock.put(
        "https://api.cloudflare.com/client/v4/zones/zone-id/dns_records/rec-id",
        json={"success": False, "errors": [{"message": "fail"}]},
    )
    result = await async_update_proxied_state(
        session, "token", "zone-id", "rec-id", "test.com", "1.2.3.4", True
    )
    assert result is False
