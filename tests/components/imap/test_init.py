"""Test the imap entry initialization."""
import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioimaplib import AUTH, NONAUTH, SELECTED, AioImapException, Response
import pytest

from homeassistant.components.imap import DOMAIN
from homeassistant.components.imap.errors import InvalidAuth, InvalidFolder
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import (
    BAD_RESPONSE,
    TEST_FETCH_RESPONSE_BINARY,
    TEST_FETCH_RESPONSE_HTML,
    TEST_FETCH_RESPONSE_INVALID_DATE,
    TEST_FETCH_RESPONSE_MULTIPART,
    TEST_FETCH_RESPONSE_TEXT_BARE,
    TEST_FETCH_RESPONSE_TEXT_OTHER,
    TEST_FETCH_RESPONSE_TEXT_PLAIN,
    TEST_FETCH_RESPONSE_TEXT_PLAIN_ALT,
    TEST_SEARCH_RESPONSE,
)
from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed


@pytest.mark.parametrize(
    "cipher_list", [None, "python_default", "modern", "intermediate"]
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_entry_startup_and_unload(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, cipher_list: str
) -> None:
    """Test imap entry startup and unload with push and polling coordinator and alternate ciphers."""
    config = MOCK_CONFIG.copy()
    if cipher_list:
        config["ssl_cipher_list"] = cipher_list

    config_entry = MockConfigEntry(domain=DOMAIN, data=config)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert await config_entry.async_unload(hass)


@pytest.mark.parametrize(
    "effect",
    [
        InvalidAuth,
        InvalidFolder,
        asyncio.TimeoutError,
    ],
)
async def test_entry_startup_fails(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    effect: Exception,
) -> None:
    """Test imap entry startup fails on invalid auth or folder."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.imap.connect_to_server",
        side_effect=effect,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize(
    ("imap_fetch", "valid_date"),
    [
        (TEST_FETCH_RESPONSE_TEXT_BARE, True),
        (TEST_FETCH_RESPONSE_TEXT_PLAIN, True),
        (TEST_FETCH_RESPONSE_TEXT_PLAIN_ALT, True),
        (TEST_FETCH_RESPONSE_INVALID_DATE, False),
        (TEST_FETCH_RESPONSE_TEXT_OTHER, True),
        (TEST_FETCH_RESPONSE_HTML, True),
        (TEST_FETCH_RESPONSE_MULTIPART, True),
        (TEST_FETCH_RESPONSE_BINARY, True),
    ],
    ids=[
        "bare",
        "plain",
        "plain_alt",
        "invalid_date",
        "other",
        "html",
        "multipart",
        "binary",
    ],
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_receiving_message_successfully(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, valid_date: bool
) -> None:
    """Test receiving a message successfully."""
    event_called = async_capture_events(hass, "imap_content")

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # we should have received one message
    assert state is not None
    assert state.state == "1"

    # we should have received one event
    assert len(event_called) == 1
    data: dict[str, Any] = event_called[0].data
    assert data["server"] == "imap.server.com"
    assert data["username"] == "email@email.com"
    assert data["search"] == "UnSeen UnDeleted"
    assert data["folder"] == "INBOX"
    assert data["sender"] == "john.doe@example.com"
    assert data["subject"] == "Test subject"
    assert data["text"]
    assert (
        valid_date
        and isinstance(data["date"], datetime)
        or not valid_date
        and data["date"] is None
    )


@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
@pytest.mark.parametrize(
    ("imap_login_state", "success"), [(AUTH, True), (NONAUTH, False)]
)
async def test_initial_authentication_error(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, success: bool
) -> None:
    """Test authentication error when starting the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) == success
    await hass.async_block_till_done()

    state = hass.states.get("sensor.imap_email_email_com")
    assert (state is not None) == success


@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
@pytest.mark.parametrize(
    ("imap_select_state", "success"), [(AUTH, False), (SELECTED, True)]
)
async def test_initial_invalid_folder_error(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, success: bool
) -> None:
    """Test invalid folder error when starting the entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id) == success
    await hass.async_block_till_done()

    state = hass.states.get("sensor.imap_email_email_com")
    assert (state is not None) == success


@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_late_authentication_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
) -> None:
    """Test authentication error handling after a search was failed."""

    # Mock an error in waiting for a pushed update
    mock_imap_protocol.wait_server_push.side_effect = AioImapException(
        "Something went wrong"
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    # Mock that the search fails, this will trigger
    # that the connection will be restarted
    # Then fail selecting the folder
    mock_imap_protocol.search.return_value = Response(*BAD_RESPONSE)
    mock_imap_protocol.login.side_effect = Response(*BAD_RESPONSE)

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert "Username or password incorrect, starting reauthentication" in caplog.text

    # we still should have an entity with an unavailable state
    state = hass.states.get("sensor.imap_email_email_com")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_late_folder_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
) -> None:
    """Test invalid folder error handling after a search was failed.

    Asserting the IMAP push coordinator.
    """
    # Mock an error in waiting for a pushed update
    mock_imap_protocol.wait_server_push.side_effect = AioImapException(
        "Something went wrong"
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Make sure we have had at least one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()

    # Mock that the search fails, this will trigger
    # that the connection will be restarted
    # Then fail selecting the folder
    mock_imap_protocol.search.return_value = Response(*BAD_RESPONSE)
    mock_imap_protocol.select.side_effect = Response(*BAD_RESPONSE)

    # Make sure we have had at least one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    assert "Selected mailbox folder is invalid" in caplog.text

    # we still should have an entity with an unavailable state
    state = hass.states.get("sensor.imap_email_email_com")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
@pytest.mark.parametrize(
    "imap_close",
    [
        AsyncMock(side_effect=AioImapException("Something went wrong")),
        AsyncMock(side_effect=asyncio.TimeoutError),
    ],
    ids=["AioImapException", "TimeoutError"],
)
async def test_handle_cleanup_exception(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
    imap_close: Exception,
) -> None:
    """Test handling an excepton during cleaning up."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.imap_email_email_com")
    # we should have an entity
    assert state is not None
    assert state.state == "0"

    # Fail cleaning up
    mock_imap_protocol.close.side_effect = imap_close

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert "Error while cleaning up imap connection" in caplog.text

    state = hass.states.get("sensor.imap_email_email_com")

    # we should have an entity with an unavailable state
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("imap_has_capability", [True], ids=["push"])
@pytest.mark.parametrize(
    "imap_wait_server_push_exception",
    [
        AioImapException("Something went wrong"),
        asyncio.TimeoutError,
    ],
    ids=["AioImapException", "TimeoutError"],
)
async def test_lost_connection_with_imap_push(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
    imap_wait_server_push_exception: AioImapException | asyncio.TimeoutError,
) -> None:
    """Test error handling when the connection is lost."""
    # Mock an error in waiting for a pushed update
    mock_imap_protocol.wait_server_push.side_effect = imap_wait_server_push_exception
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert "Lost imap.server.com (will attempt to reconnect after 10 s)" in caplog.text

    state = hass.states.get("sensor.imap_email_email_com")
    # Our entity should keep its current state as this
    assert state is not None
    assert state.state == "0"


@pytest.mark.parametrize("imap_has_capability", [True], ids=["push"])
async def test_fetch_number_of_messages(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
) -> None:
    """Test _async_fetch_number_of_messages fails with push coordinator."""
    # Mock an error in waiting for a pushed update
    mock_imap_protocol.search.return_value = Response(*BAD_RESPONSE)
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we wait for the backoff time
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    assert "Invalid response for search" in caplog.text

    state = hass.states.get("sensor.imap_email_email_com")
    # we should have an entity with an unavailable state
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
