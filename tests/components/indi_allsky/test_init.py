"""Tests for the INDI Allsky integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import aiohttp
from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
import yarl

from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import setup_integration


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.listen.assert_called_once_with(auto_reconnect=True)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_indi_allsky_client.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    "method_name",
    ["fetch_image", "connect"],
)
async def test_setup_failure_retry(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    method_name: str,
) -> None:
    """Test that an API connection failure during initial setup places entry in retry state."""
    getattr(
        mock_indi_allsky_client, method_name
    ).side_effect = IndiAllSkyConnectionError("Cannot connect to INDI Allsky server")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_failure_auth(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an authentication failure during initial setup marks the entry as SETUP_ERROR."""
    mock_indi_allsky_client.fetch_image.side_effect = IndiAllSkyAuthError(
        "Invalid username or password"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_with_credentials(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
) -> None:
    """Test that configured credentials are forwarded to IndiAllSkyClient."""
    entry = MockConfigEntry(
        domain="indi_allsky",
        title="INDI Allsky (127.0.0.1)",
        data={
            "host": "127.0.0.1",
            "port": 443,
            "ssl": True,
            "verify_ssl": True,
            "username": "test_username",
            "password": "test_password",
        },
        entry_id="test_entry_credentials",
    )
    with patch(
        "homeassistant.components.indi_allsky.coordinator.IndiAllSkyClient",
        return_value=mock_indi_allsky_client,
    ) as mock_client_cls:
        await setup_integration(hass, entry)
        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args.kwargs["username"] == "test_username"
        assert mock_client_cls.call_args.kwargs["password"] == "test_password"


async def test_entry_session_accepts_ip_cookies(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the entry session uses a cookie jar that accepts cookies from IP hosts."""
    with patch(
        "homeassistant.components.indi_allsky.coordinator.async_create_clientsession",
        wraps=async_create_clientsession,
    ) as mock_create_session:
        await setup_integration(hass, mock_config_entry)

    mock_create_session.assert_called_once()
    kwargs = mock_create_session.call_args.kwargs
    assert kwargs["verify_ssl"] is True
    cookie_jar: aiohttp.CookieJar = kwargs["cookie_jar"]
    assert mock_config_entry.runtime_data.session.cookie_jar is cookie_jar

    login_url = yarl.URL("https://127.0.0.1/indi-allsky/login")
    cookie_jar.update_cookies({"session": "abc"}, response_url=login_url)
    assert "session" in cookie_jar.filter_cookies(login_url)


async def test_background_sensor_fetch_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that authentication failure during background sensor fetch triggers reauth."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.side_effect = IndiAllSkyAuthError(
        "Unauthorized"
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": SOURCE_REAUTH}
    )
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_background_sensor_fetch_generic_error_ignored(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that generic error during background sensor fetch is suppressed."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.side_effect = IndiAllSkyConnectionError(
        "Connection lost"
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
