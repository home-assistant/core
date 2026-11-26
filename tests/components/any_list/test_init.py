"""Tests for AnyList integration setup."""

import asyncio
import logging
from unittest.mock import MagicMock

from aioanylist import AuthenticationError, AuthTokens, TransportError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import homeassistant as ha_component
from homeassistant.components.any_list.const import CONF_REFRESH_TOKEN, CONF_USER_LOCALE
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACCESS_TOKEN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import USER_ID


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


async def test_setup_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test invalid stored credentials fail setup and start a reauth flow."""
    mock_anylist_client.load.side_effect = AuthenticationError()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


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
        logging.INFO, logger="homeassistant.components.any_list.coordinator"
    )
    error = TransportError("AnyList is unreachable")
    status_listener(error)
    status_listener(error)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"
    assert (
        caplog.record_tuples.count(
            (
                "homeassistant.components.any_list.coordinator",
                logging.INFO,
                "AnyList is unavailable",
            )
        )
        == 1
    )

    status_listener(None)
    status_listener(None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state != "unavailable"
    assert caplog.text.count("Fetching any_list data recovered") == 1


async def test_runtime_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Test a runtime authentication failure starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    status_listener = mock_anylist_client.sync_status_listener
    assert status_listener is not None

    entity_id = "todo.groceries"
    assert hass.states.get(entity_id).state != "unavailable"

    status_listener(AuthenticationError())
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_socket_outage_requires_successful_catchup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """Only fresh data on a live socket restores availability."""
    await setup_integration(hass, mock_config_entry)
    on_error = mock_anylist_client.realtime_error_listener
    on_sync_status = mock_anylist_client.sync_status_listener

    mock_anylist_client.realtime.connected.clear()
    on_error(TransportError())
    await hass.async_block_till_done()
    assert hass.states.get("todo.groceries").state == "unavailable"

    on_sync_status(None)
    await hass.async_block_till_done()
    assert hass.states.get("todo.groceries").state == "unavailable"

    mock_anylist_client.realtime.connected.set()
    on_sync_status(TransportError())
    await hass.async_block_till_done()
    assert hass.states.get("todo.groceries").state == "unavailable"

    on_sync_status(None)
    await hass.async_block_till_done()
    assert hass.states.get("todo.groceries").state != "unavailable"


async def test_socket_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """An expired socket session can initiate reauth during reconnect."""
    await setup_integration(hass, mock_config_entry)
    handler = mock_anylist_client.realtime_error_listener
    handler(AuthenticationError())
    handler(AuthenticationError())
    await hass.async_block_till_done()

    assert hass.states.get("todo.groceries").state == "unavailable"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_socket_setup_timeout_retries_and_closes_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setup does not wait indefinitely for its first socket connection."""

    async def load(**kwargs: object) -> None:
        await asyncio.Event().wait()

    mock_anylist_client.load.side_effect = load
    monkeypatch.setattr(
        "homeassistant.components.any_list.coordinator.SETUP_TIMEOUT", 0
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_anylist_client.close.assert_awaited_once()


async def test_socket_closes_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """A lost socket during initial setup defers setup and closes the client."""

    async def load(**kwargs: object) -> None:
        mock_anylist_client.realtime.connected.clear()
        mock_anylist_client.realtime_error_listener(TransportError())

    mock_anylist_client.load.side_effect = load
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_anylist_client.close.assert_awaited_once()


async def test_update_entity_does_not_restore_availability_before_catchup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_anylist_client: MagicMock,
) -> None:
    """A manual refresh cannot recover an outage by publishing cached data."""
    assert await async_setup_component(hass, ha_component.DOMAIN, {})
    await setup_integration(hass, mock_config_entry)
    entity_id = "todo.groceries"

    mock_anylist_client.realtime.connected.clear()
    mock_anylist_client.realtime_error_listener(TransportError())
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_anylist_client.realtime.connected.set()
    await hass.services.async_call(
        ha_component.DOMAIN,
        ha_component.SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    mock_anylist_client.sync_status_listener(None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
