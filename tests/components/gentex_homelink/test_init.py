"""Test that the integration is initialized correctly."""

import http
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, RequestInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
import homeassistant.helpers.device_registry as dr

from . import setup_integration, update_callback

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device is registered correctly."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "TestDevice"), mock_config_entry.entry_id
    )
    assert device
    assert device == snapshot


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_reload_sync(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the config entry is reloaded when a requestSync request is sent."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload") as async_reload_mock:
        await update_callback(
            hass,
            mock_mqtt_provider,
            "requestSync",
            {},
        )

        async_reload_mock.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the entry can be loaded and unloaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exc", "expected_state"),
    [
        (
            OAuth2TokenRequestReauthError(
                request_info=RequestInfo("", "POST", {}, ""),
                status=http.HTTPStatus.UNAUTHORIZED,
                domain=DOMAIN,
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            OAuth2TokenRequestError(
                request_info=RequestInfo("", "POST", {}, ""),
                status=http.HTTPStatus.INTERNAL_SERVER_ERROR,
                domain=DOMAIN,
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["auth_failure", "server_error"],
)
async def test_setup_entry_token_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exc: OAuth2TokenRequestError,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry fails when token validation fails."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=exc,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_entry_token_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry retries when token validation has a connection error."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientConnectionError(),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
