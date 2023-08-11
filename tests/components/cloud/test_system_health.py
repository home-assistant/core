"""Test cloud system health."""
import asyncio
from unittest.mock import Mock

from aiohttp import ClientError
from hass_nabucasa.remote import CertificateStatus

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_cloud_system_health(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test cloud system health."""
    aioclient_mock.get("https://cloud.bla.com/status", text="")
    aioclient_mock.get("https://cert-server/directory", text="")
    aioclient_mock.get(
        "https://cognito-idp.us-east-1.amazonaws.com/AAAA/.well-known/jwks.json",
        exc=ClientError,
    )
    hass.config.components.add("cloud")
    assert await async_setup_component(hass, "system_health", {})
    now = utcnow()

    hass.data["cloud"] = Mock(
        region="us-east-1",
        user_pool_id="AAAA",
        relayer_server="cloud.bla.com",
        acme_server="cert-server",
        is_logged_in=True,
        remote=Mock(
            is_connected=False,
            snitun_server="us-west-1",
            certificate_status=CertificateStatus.READY,
        ),
        expiration_date=now,
        is_connected=True,
        client=Mock(
            relayer_region="xx-earth-616",
            prefs=Mock(
                remote_enabled=True,
                alexa_enabled=True,
                google_enabled=False,
            ),
        ),
    )

    info = await get_system_health_info(hass, "cloud")

    for key, val in info.items():
        if asyncio.iscoroutine(val):
            info[key] = await val

    assert info == {
        "logged_in": True,
        "subscription_expiration": now,
        "certificate_status": "ready",
        "relayer_connected": True,
        "relayer_region": "xx-earth-616",
        "remote_enabled": True,
        "remote_connected": False,
        "remote_server": "us-west-1",
        "alexa_enabled": True,
        "google_enabled": False,
        "can_reach_cert_server": "ok",
        "can_reach_cloud_auth": {"type": "failed", "error": "unreachable"},
        "can_reach_cloud": "ok",
    }
