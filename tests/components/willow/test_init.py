"""Tests for the Willow integration setup."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.willow.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.willow.exceptions import WillowAuthError
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("setup_credentials")

PANEL_REGISTERED = "panel_registered"


async def test_setup_unload(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][PANEL_REGISTERED] is True

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.data[DOMAIN][PANEL_REGISTERED] is False


async def test_setup_retries_on_api_failure(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth API failure surfaces as a setup retry."""
    mock_willow_client.get_devices.side_effect = TimeoutError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_reauth_on_authentication_error(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A rejected access token at setup starts a reauth flow."""
    mock_willow_client.get_profile.side_effect = WillowAuthError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


@pytest.mark.usefixtures("mock_willow_client")
async def test_setup_retries_when_implementation_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Missing OAuth2 implementation defers setup as not-ready."""
    with patch(
        "homeassistant.components.willow.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError("gone"),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_poll_reauth_on_authentication_error(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A rejected access token during the poll starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    mock_willow_client.get_profile.side_effect = WillowAuthError

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_periodic_poll_fails_on_api_error(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A non-auth API error during periodic refresh marks the coordinator failed."""
    await setup_integration(hass, mock_config_entry)
    mock_willow_client.get_devices.side_effect = TimeoutError("boom")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is False
