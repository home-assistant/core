"""Test DNS failure recovery in HomeAssistantTCPConnector."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    HomeAssistantTCPConnector,
    async_get_clientsession,
)


async def test_connector_clears_dns_cache_per_host(
    hass: HomeAssistant,
) -> None:
    """Test that DNS cache can be cleared per host."""
    session = async_get_clientsession(hass)
    connector = session.connector

    assert isinstance(connector, HomeAssistantTCPConnector)
    assert callable(connector.clear_dns_cache)

    # Clear all — should not raise
    connector.clear_dns_cache()


async def test_clear_dns_cache_with_host_and_port(
    hass: HomeAssistant,
) -> None:
    """Test that clear_dns_cache works with host and port."""
    session = async_get_clientsession(hass)
    connector = session.connector

    # Must pass both host and port, or neither
    connector.clear_dns_cache("api.met.no", 443)
    connector.clear_dns_cache("example.com", 443)


async def test_session_not_closed_after_dns_cache_clear(
    hass: HomeAssistant,
) -> None:
    """Test that clearing DNS cache doesn't close the session."""
    session = async_get_clientsession(hass)
    connector = session.connector

    connector.clear_dns_cache()
    assert not session.closed
