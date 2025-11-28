"""Test that the integration is initialized correctly."""

import time
from unittest.mock import patch

from homeassistant.components import gentex_homelink
from homeassistant.components.gentex_homelink.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


async def test_load_unload_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the entry can be loaded and unloaded."""
    with patch("homeassistant.components.gentex_homelink.MQTTProvider", autospec=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=None,
            version=1,
            data={
                "auth_implementation": "gentex_homelink",
                "token": {"refresh_token": "refresh"},
            },
        )
        entry.add_to_hass(hass)

        aioclient_mock.clear_requests()
        aioclient_mock.post(
            OAUTH2_TOKEN,
            json={
                "access_token": "updated-access-token",
                "refresh_token": "updated-refresh-token",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            },
        )
        assert await async_setup_component(hass, DOMAIN, {}) is True, (
            "Component is not set up"
        )

        assert await gentex_homelink.async_unload_entry(hass, entry), (
            "Component not unloaded"
        )
