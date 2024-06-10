"""Tests for the auth component."""

from typing import Any

from homeassistant import auth
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import ensure_auth_manager_loaded
from tests.test_util import mock_real_ip
from tests.typing import ClientSessionGenerator

BASE_CONFIG = [
    {
        "name": "Example",
        "type": "insecure_example",
        "users": [
            {"username": "test-user", "password": "test-pass", "name": "Test Name"}
        ],
    }
]

EMPTY_CONFIG = []


async def async_setup_auth(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    provider_configs: list[dict[str, Any]] = BASE_CONFIG,
    module_configs=EMPTY_CONFIG,
    setup_api: bool = False,
    custom_ip: str | None = None,
):
    """Set up authentication and create an HTTP client."""
    hass.auth = await auth.auth_manager_from_config(
        hass, provider_configs, module_configs
    )
    ensure_auth_manager_loaded(hass.auth)
    await async_setup_component(hass, "auth", {})
    if setup_api:
        await async_setup_component(hass, "api", {})
    if custom_ip:
        mock_real_ip(hass.http.app)(custom_ip)
    return await aiohttp_client(hass.http.app)
