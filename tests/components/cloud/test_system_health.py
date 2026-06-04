"""Test cloud system health."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

from aiohttp import ClientError
from hass_nabucasa.iot_base import DisconnectReason
from hass_nabucasa.remote import Certificate, CertificateStatus

from homeassistant.components.cloud.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import UTC

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_cloud_system_health(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test cloud system health."""
    aioclient_mock.get("https://cloud.bla.com/status", text="")
    aioclient_mock.get("https://cert-server/directory", text="")
    aioclient_mock.get(
        "https://cognito-idp.us-east-1.amazonaws.com/AAAA/.well-known/jwks.json",
        exc=ClientError,
    )
    assert await async_setup_component(hass, "system_health", {})
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "user_pool_id": "AAAA",
                "region": "us-east-1",
                "acme_server": "cert-server",
                "relayer_server": "cloud.bla.com",
            },
        },
    )
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    cloud.remote.snitun_server = "us-west-1"
    cloud.remote.certificate_status = CertificateStatus.READY
    cloud.remote.certificate = None
    cloud.remote.latency_by_location = {}
    cloud.iot.state = "connected"
    cloud.iot.tries = 0
    cloud.iot.last_disconnect_reason = None

    await cloud.client.async_system_message({"region": "xx-earth-616"})
    await set_cloud_prefs(
        {
            "alexa_enabled": True,
            "google_enabled": False,
            "remote_enabled": True,
            "cloud_ice_servers_enabled": True,
        }
    )

    info = await get_system_health_info(hass, "cloud")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "logged_in": True,
        "subscription_expiration": cloud.expiration_date,
        "certificate_status": CertificateStatus.READY,
        "relayer_connected": True,
        "relayer_region": "xx-earth-616",
        "remote_enabled": True,
        "remote_connected": False,
        "remote_server": "us-west-1",
        "alexa_enabled": True,
        "google_enabled": False,
        "cloud_ice_servers_enabled": True,
        "can_reach_cert_server": "ok",
        "can_reach_cloud_auth": {"type": "failed", "error": "unreachable"},
        "can_reach_cloud": "ok",
        "instance_id": cloud.client.prefs.instance_id,
        "iot_state": "connected",
        "iot_tries": 0,
    }


async def test_cloud_system_health_with_cert_and_disconnect(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> None:
    """Test cloud system health with certificate details and disconnect reason."""
    aioclient_mock.get("https://cloud.bla.com/status", text="")
    aioclient_mock.get("https://cert-server/directory", text="")
    aioclient_mock.get(
        "https://cognito-idp.us-east-1.amazonaws.com/AAAA/.well-known/jwks.json",
        text="",
    )
    assert await async_setup_component(hass, "system_health", {})
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "user_pool_id": "AAAA",
                "region": "us-east-1",
                "acme_server": "cert-server",
                "relayer_server": "cloud.bla.com",
            },
        },
    )
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")

    expire = datetime(2026, 8, 1, tzinfo=UTC)
    cloud.remote.snitun_server = "eu-central-1"
    cloud.remote.certificate_status = CertificateStatus.READY
    cloud.remote.certificate = Certificate(
        common_name="my-home.ui.nabu.casa",
        expire_date=expire,
        fingerprint="abc123def456",
        alternative_names=["custom.example.com"],
    )
    cloud.remote.latency_by_location = {"fra": {"avg": 12.4}, "iad": {"avg": None}}
    cloud.iot.state = "connected"
    cloud.iot.tries = 2
    cloud.iot.last_disconnect_reason = DisconnectReason(
        clean=False, reason="ping_timeout"
    )

    await set_cloud_prefs({"remote_enabled": True})

    info = await get_system_health_info(hass, "cloud")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info["certificate_expire_date"] == expire
    assert info["certificate_fingerprint"] == "abc123def456"
    assert info["certificate_alternative_names"] == ["custom.example.com"]
    assert info["iot_last_disconnect_clean"] is False
    assert info["iot_last_disconnect_reason"] == "ping_timeout"
    assert info["iot_tries"] == 2
    assert info["remote_latency_avg_by_location"]["fra"] == 12.4
    assert info["remote_latency_avg_by_location"]["iad"] is None
