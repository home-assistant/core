"""Tests for various Plex services."""
import pytest

from homeassistant.components.plex.const import (
    CONF_SERVER,
    CONF_SERVER_IDENTIFIER,
    DOMAIN,
    PLEX_SERVER_CONFIG,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SCAN_CLIENTS,
)
from homeassistant.const import CONF_URL
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_OPTIONS, SECONDARY_DATA

from tests.common import MockConfigEntry


async def test_refresh_library(
    hass,
    mock_plex_server,
    setup_plex_server,
    requests_mock,
    empty_payload,
    plex_server_accounts,
    plex_server_base,
):
    """Test refresh_library service call."""
    url = mock_plex_server.url_in_use
    refresh = requests_mock.get(f"{url}/library/sections/1/refresh", status_code=200)

    # Test with non-existent server
    with pytest.raises(HomeAssistantError):
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"server_name": "Not a Server", "library_name": "Movies"},
            True,
        )
    assert not refresh.called

    # Test with non-existent library
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Not a Library"},
        True,
    )
    assert not refresh.called

    # Test with valid library
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        {"library_name": "Movies"},
        True,
    )
    assert refresh.call_count == 1

    # Add a second configured server
    secondary_url = SECONDARY_DATA[PLEX_SERVER_CONFIG][CONF_URL]
    secondary_name = SECONDARY_DATA[CONF_SERVER]
    secondary_id = SECONDARY_DATA[CONF_SERVER_IDENTIFIER]
    requests_mock.get(
        secondary_url,
        text=plex_server_base.format(
            name=secondary_name, machine_identifier=secondary_id
        ),
    )
    requests_mock.get(f"{secondary_url}/accounts", text=plex_server_accounts)
    requests_mock.get(f"{secondary_url}/clients", text=empty_payload)
    requests_mock.get(f"{secondary_url}/status/sessions", text=empty_payload)

    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data=SECONDARY_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=SECONDARY_DATA["server_id"],
    )

    await setup_plex_server(config_entry=entry_2)

    # Test multiple servers available but none specified
    with pytest.raises(HomeAssistantError) as excinfo:
        assert await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH_LIBRARY,
            {"library_name": "Movies"},
            True,
        )
    assert "Multiple Plex servers configured" in str(excinfo.value)
    assert refresh.call_count == 1


async def test_scan_clients(hass, mock_plex_server):
    """Test scan_for_clients service call."""
    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SCAN_CLIENTS,
        blocking=True,
    )
