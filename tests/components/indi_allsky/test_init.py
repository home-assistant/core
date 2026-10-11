"""Tests for the INDI Allsky integration."""

from unittest.mock import AsyncMock, patch

from aioindiallsky import IndiAllSkyAuthError, IndiAllSkyConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


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


async def test_background_sensor_fetch_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that authentication failure during background sensor fetch triggers reauth."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.side_effect = IndiAllSkyAuthError(
        "Unauthorized"
    )

    with patch.object(
        mock_config_entry, "async_start_reauth"
    ) as mock_async_start_reauth:
        coordinator = mock_config_entry.runtime_data
        coordinator._async_trigger_fetch_sensors()
        await hass.async_block_till_done(wait_background_tasks=True)

    mock_async_start_reauth.assert_called_once_with(hass)


async def test_background_sensor_fetch_generic_error_ignored(
    hass: HomeAssistant,
    mock_indi_allsky_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that generic error during background sensor fetch is suppressed."""
    await setup_integration(hass, mock_config_entry)

    mock_indi_allsky_client.fetch_sensors.side_effect = IndiAllSkyConnectionError(
        "Connection lost"
    )

    coordinator = mock_config_entry.runtime_data
    coordinator._async_trigger_fetch_sensors()
    await hass.async_block_till_done(wait_background_tasks=True)
