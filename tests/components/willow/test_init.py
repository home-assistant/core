"""Tests for the Willow integration setup."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywillow import WillowApiError, WillowAuthError

from homeassistant.components.willow.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("setup_credentials")

ENTITY_ID = "sensor.kitchen_basil_temperature"


async def test_setup_unload(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The integration loads and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_on_api_failure(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A non-auth API failure surfaces as a setup retry."""
    mock_willow_client.get_devices.side_effect = TimeoutError("boom")

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_error_on_authentication_error(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A rejected access token at setup puts the entry in an error state."""
    mock_willow_client.get_profile.side_effect = WillowAuthError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(WillowAuthError, id="auth_error"),
        pytest.param(TimeoutError("boom"), id="api_error"),
        pytest.param(WillowApiError("boom"), id="willow_api_error"),
    ],
)
async def test_poll_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    mock_willow_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """A failed poll marks the sensors unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_willow_client.get_devices.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
