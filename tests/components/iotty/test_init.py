"""Tests for the iotty integration."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from iottycloud.errors import (
    BadRequestException,
    CloudError,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.iotty.const import DOMAIN
from homeassistant.components.iotty.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)


async def test_load_unload_coordinator_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MagicMock,
    local_oauth_impl,
) -> None:
    """Test the configuration entry loading/unloading."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_coordinator.assert_called_once()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    method_call = mock_coordinator.method_calls[0]
    name, _, _ = method_call
    assert name == "().async_config_entry_first_refresh"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iotty.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload_iottyproxy_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iotty: MagicMock,
    local_oauth_impl,
    mock_config_entries_async_forward_entry_setup,
) -> None:
    """Test the configuration entry loading/unloading."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_iotty.assert_called_once()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    method_call = mock_iotty.method_calls[0]
    name, _, _ = method_call
    assert name == "().get_devices"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


def _assert_reauth_started(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Assert a single reauth flow was started for the entry."""
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


async def test_setup_token_refresh_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a rejected token refresh during setup starts a reauth flow."""
    aioclient_mock.post("https://token.url", status=HTTPStatus.UNAUTHORIZED)
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    _assert_reauth_started(hass, mock_config_entry)


async def test_setup_token_refresh_transient_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a transient token refresh failure during setup retries setup."""
    aioclient_mock.post("https://token.url", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_setup_api_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    mock_get_devices_nodevices: AsyncMock,
) -> None:
    """Test an unauthorized API response during setup starts a reauth flow."""
    mock_get_devices_nodevices.side_effect = UnauthorizedException
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    _assert_reauth_started(hass, mock_config_entry)


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(BadRequestException, id="bad_request"),
        pytest.param(ForbiddenException, id="forbidden"),
        pytest.param(NotFoundException, id="not_found"),
        pytest.param(CloudError, id="cloud_error"),
    ],
)
async def test_setup_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    mock_get_devices_nodevices: AsyncMock,
    side_effect: type[Exception],
) -> None:
    """Test other API errors during setup retry setup."""
    mock_get_devices_nodevices.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.usefixtures("mock_get_status_filled")
async def test_update_api_auth_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: config_entry_oauth2_flow.LocalOAuth2Implementation,
    mock_get_devices_twolightswitches: AsyncMock,
) -> None:
    """Test an unauthorized API response during a refresh starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_get_devices_twolightswitches.side_effect = UnauthorizedException
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    _assert_reauth_started(hass, mock_config_entry)
