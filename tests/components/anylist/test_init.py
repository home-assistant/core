"""Tests for AnyList integration setup."""

import logging
from unittest.mock import MagicMock

from aioanylist import AuthenticationError, AuthTokens, TransportError
import pytest

from homeassistant.components.anylist.const import CONF_REFRESH_TOKEN, CONF_USER_LOCALE
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import USER_ID

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test setup starts realtime sync and unload closes the client."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_anylist_client.load.assert_awaited_once_with(
        realtime=True, load_tag_data=False
    )
    mock_anylist_client.sync.add_listener.assert_called_once()
    mock_anylist_client.sync.add_status_listener.assert_called_once()
    assert mock_anylist_client.sync_listener is not None
    assert mock_anylist_client.sync_status_listener is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_anylist_client.close.assert_awaited_once()


async def test_unload_ignores_close_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a timeout while closing AnyList does not block unload."""
    await setup_integration(hass, mock_config_entry)
    mock_anylist_client.close.side_effect = TimeoutError()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_anylist_client.close.assert_awaited_once()


async def test_rotated_tokens_are_persisted(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test rotated AnyList tokens are persisted immediately."""
    await setup_integration(hass, mock_config_entry)

    callback = mock_anylist_client.token_callback
    assert callback is not None
    callback(
        AuthTokens(
            user_id=USER_ID,
            access_token="new-access",
            refresh_token="new-refresh",
            user_locale="de-DE",
        )
    )

    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new-access"
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-refresh"
    assert mock_config_entry.data[CONF_USER_LOCALE] == "de-DE"


async def test_setup_starts_reauth_on_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test invalid stored credentials start reauthentication."""
    mock_anylist_client.load.side_effect = AuthenticationError()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test temporary AnyList failures defer setup."""
    mock_anylist_client.load.side_effect = TransportError()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_runtime_sync_failure_marks_entities_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test runtime AnyList sync health controls availability without log spam."""
    await setup_integration(hass, mock_config_entry)
    status_listener = mock_anylist_client.sync_status_listener
    assert status_listener is not None

    entity_id = "todo.groceries"
    assert hass.states.get(entity_id).state != "unavailable"

    caplog.set_level(
        logging.INFO, logger="homeassistant.components.anylist.coordinator"
    )
    error = TransportError("AnyList is unreachable")
    status_listener(error)
    status_listener(error)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"
    assert (
        caplog.text.count("Error requesting anylist data: AnyList is unreachable") == 1
    )

    status_listener(None)
    status_listener(None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != "unavailable"
    assert caplog.text.count("Fetching anylist data recovered") == 1


async def test_runtime_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a runtime authentication failure starts reauthentication."""
    await setup_integration(hass, mock_config_entry)
    status_listener = mock_anylist_client.sync_status_listener
    assert status_listener is not None

    status_listener(AuthenticationError())
    await hass.async_block_till_done()

    assert any(
        flow["context"]["source"] == SOURCE_REAUTH
        for flow in hass.config_entries.flow.async_progress()
    )
