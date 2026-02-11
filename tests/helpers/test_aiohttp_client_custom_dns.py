"""Test the aiohttp client helper with custom DNS."""

import aiohttp
import pytest

from homeassistant.components.http import CONF_NAMESERVERS, DOMAIN as HTTP_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client as client
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("mock_async_zeroconf", "disable_mock_zeroconf_resolver")
async def test_resolver_uses_configured_nameservers(hass: HomeAssistant) -> None:
    """Test that the resolver uses the configured nameservers."""
    assert await async_setup_component(
        hass,
        HTTP_DOMAIN,
        {HTTP_DOMAIN: {CONF_NAMESERVERS: ["1.1.1.1", "1.0.0.1"]}},
    )

    session = client.async_get_clientsession(hass)
    assert isinstance(session._connector, aiohttp.TCPConnector)
    resolver = session._connector._resolver
    assert isinstance(resolver, client.HassAsyncDNSResolver)

    # AsyncDualMDNSResolver passes nameservers to the underlying aiohttp Resolver
    # We can check if the nameservers are correctly set in the resolver
    # resolver._resolver is the aiodns.DNSResolver instance
    assert "1.1.1.1" in resolver._resolver.nameservers
    assert "1.0.0.1" in resolver._resolver.nameservers
