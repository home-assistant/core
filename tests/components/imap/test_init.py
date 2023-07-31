"""Test the imap entry initialization."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from aioimaplib import AUTH, NONAUTH, SELECTED, AioImapException, Response
import pytest

from homeassistant.components.imap import DOMAIN
from homeassistant.components.imap.errors import InvalidAuth, InvalidFolder
from homeassistant.components.sensor.const import SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import (
    BAD_RESPONSE,
    EMPTY_SEARCH_RESPONSE,
    TEST_FETCH_RESPONSE_BINARY,
    TEST_FETCH_RESPONSE_HTML,
    TEST_FETCH_RESPONSE_INVALID_DATE1,
    TEST_FETCH_RESPONSE_INVALID_DATE2,
    TEST_FETCH_RESPONSE_INVALID_DATE3,
    TEST_FETCH_RESPONSE_MULTIPART,
    TEST_FETCH_RESPONSE_NO_SUBJECT_TO_FROM,
    TEST_FETCH_RESPONSE_TEXT_BARE,
    TEST_FETCH_RESPONSE_TEXT_OTHER,
    TEST_FETCH_RESPONSE_TEXT_PLAIN,
    TEST_FETCH_RESPONSE_TEXT_PLAIN_ALT,
    TEST_SEARCH_RESPONSE,
)
from .test_config_flow import MOCK_CONFIG

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed


@pytest.mark.parametrize(
    ("cipher_list", "verify_ssl", "enable_push"),
    [
        (None, None, None),
        ("python_default", True, None),
        ("python_default", False, None),
        ("modern", True, None),
        ("intermediate", True, None),
        (None, None, False),
        (None, None, True),
        ("python_default", True, False),
        ("python_default", False, True),
    ],
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_entry_startup_and_unload(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    cipher_list: str | None,
    verify_ssl: bool | None,
    enable_push: bool | None,
) -> None:
    """Test imap entry startup and unload with push and polling coordinator and alternate ciphers."""
    config = MOCK_CONFIG.copy()
    if cipher_list is not None:
        config["ssl_cipher_list"] = cipher_list
    if verify_ssl is not None:
        config["verify_ssl"] = verify_ssl
    if enable_push is not None:
        config["enable_push"] = enable_push

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
        (TEST_FETCH_RESPONSE_INVALID_DATE1, False),
        (TEST_FETCH_RESPONSE_INVALID_DATE2, False),
        (TEST_FETCH_RESPONSE_INVALID_DATE3, False),
        (TEST_FETCH_RESPONSE_TEXT_OTHER, True),
        (TEST_FETCH_RESPONSE_HTML, True),
        (TEST_FETCH_RESPONSE_MULTIPART, True),
        (TEST_FETCH_RESPONSE_BINARY, True),
    ],
    ids=[
        "bare",
        "plain",
        "plain_alt",
        "invalid_date1",
        "invalid_date2",
        "invalid_date3",
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
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT

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


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize("imap_fetch", [TEST_FETCH_RESPONSE_NO_SUBJECT_TO_FROM])
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_receiving_message_no_subject_to_from(
    hass: HomeAssistant, mock_imap_protocol: MagicMock
) -> None:
    """Test receiving a message successfully without subject, to and from in body."""
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
    assert data["sender"] == ""
    assert data["subject"] == ""
    assert data["date"] == datetime(
        2023, 3, 24, 13, 52, tzinfo=timezone(timedelta(seconds=3600))
    )
    assert data["text"] == "Test body\r\n\r\n"
    assert data["headers"]["Return-Path"] == ("<john.doe@example.com>",)
    assert data["headers"]["Delivered-To"] == ("notify@example.com",)


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


@patch("homeassistant.components.imap.coordinator.MAX_ERRORS", 1)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_late_authentication_retry(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_imap_protocol: MagicMock,
) -> None:
    """Test retrying authentication after a search was failed."""

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
    assert "Authentication failed, retrying" in caplog.text

    # we still should have an entity with an unavailable state
    state = hass.states.get("sensor.imap_email_email_com")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@patch("homeassistant.components.imap.coordinator.MAX_ERRORS", 0)
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


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize(
    ("imap_fetch", "valid_date"),
    [(TEST_FETCH_RESPONSE_TEXT_PLAIN, True)],
    ids=["plain"],
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_reset_last_message(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, valid_date: bool
) -> None:
    """Test receiving a message successfully."""
    event = asyncio.Event()  # needed for pushed coordinator to make a new loop

    async def _sleep_till_event() -> None:
        """Simulate imap server waiting for pushes message and keep the push loop going.

        Needed for pushed coordinator only.
        """
        nonlocal event
        await event.wait()
        event.clear()
        mock_imap_protocol.idle_start.return_value = AsyncMock()()

    # Make sure we make another cycle (needed for pushed coordinator)
    mock_imap_protocol.idle_start.return_value = AsyncMock()()
    # Mock we wait till we push an update (needed for pushed coordinator)
    mock_imap_protocol.wait_server_push.side_effect = _sleep_till_event

    event_called = async_capture_events(hass, "imap_content")

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # We should have received one message
    assert state is not None
    assert state.state == "1"

    # We should have received one event
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

    # Simulate an update where no messages are found (needed for pushed coordinator)
    mock_imap_protocol.search.return_value = Response(*EMPTY_SEARCH_RESPONSE)

    # Make sure we have an update
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))

    # Awake loop (needed for pushed coordinator)
    event.set()

    await hass.async_block_till_done()

    state = hass.states.get("sensor.imap_email_email_com")
    # We should have message
    assert state is not None
    assert state.state == "0"
    # No new events should be called
    assert len(event_called) == 1

    # Simulate an update where with the original message
    mock_imap_protocol.search.return_value = Response(*TEST_SEARCH_RESPONSE)
    # Make sure we have an update again with the same UID
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))

    # Awake loop (needed for pushed coordinator)
    event.set()

    await hass.async_block_till_done()

    state = hass.states.get("sensor.imap_email_email_com")
    # We should have received one message
    assert state is not None
    assert state.state == "1"
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # One new event
    assert len(event_called) == 2


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize(
    "imap_fetch", [(TEST_FETCH_RESPONSE_TEXT_PLAIN)], ids=["plain"]
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
@patch("homeassistant.components.imap.coordinator.MAX_EVENT_DATA_BYTES", 500)
async def test_event_skipped_message_too_large(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test skipping event when message is to large."""
    event_called = async_capture_events(hass, "imap_content")

    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # We should have received one message
    assert state is not None
    assert state.state == "1"
    assert len(event_called) == 0
    assert "Custom imap_content event skipped" in caplog.text


@pytest.mark.parametrize("imap_search", [TEST_SEARCH_RESPONSE])
@pytest.mark.parametrize(
    "imap_fetch", [(TEST_FETCH_RESPONSE_TEXT_PLAIN)], ids=["plain"]
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
async def test_message_is_truncated(
    hass: HomeAssistant, mock_imap_protocol: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test truncating message text in event data."""
    event_called = async_capture_events(hass, "imap_content")

    config = MOCK_CONFIG.copy()

    # Mock the max message size to test it is truncated
    config["max_message_size"] = 3
    config_entry = MockConfigEntry(domain=DOMAIN, data=config)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    # Make sure we have had one update (when polling)
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    state = hass.states.get("sensor.imap_email_email_com")
    # We should have received one message
    assert state is not None
    assert state.state == "1"
    assert len(event_called) == 1

    event_data = event_called[0].data
    assert len(event_data["text"]) == 3


@pytest.mark.parametrize(
    ("imap_search", "imap_fetch"),
    [(TEST_SEARCH_RESPONSE, TEST_FETCH_RESPONSE_TEXT_PLAIN)],
    ids=["plain"],
)
@pytest.mark.parametrize("imap_has_capability", [True, False], ids=["push", "poll"])
@pytest.mark.parametrize(
    ("custom_template", "result", "error"),
    [
        ("{{ subject }}", "Test subject", None),
        ('{{ "@example.com" in sender }}', True, None),
        ("{% bad template }}", None, "Error rendering imap custom template"),
    ],
    ids=["subject_test", "sender_filter", "template_error"],
)
async def test_custom_template(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    caplog: pytest.LogCaptureFixture,
    custom_template: str,
    result: str | bool | None,
    error: str | None,
) -> None:
    """Test the custom template event data."""
    event_called = async_capture_events(hass, "imap_content")

    config = MOCK_CONFIG.copy()
    config["custom_event_data_template"] = custom_template
    config_entry = MockConfigEntry(domain=DOMAIN, data=config)
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
    assert data["custom"] == result
    assert error in caplog.text if error is not None else True


@pytest.mark.parametrize(
    ("imap_search", "imap_fetch"),
    [(TEST_SEARCH_RESPONSE, TEST_FETCH_RESPONSE_TEXT_PLAIN)],
)
@pytest.mark.parametrize(
    ("imap_has_capability", "enable_push", "should_poll"),
    [
        (True, False, True),
        (False, False, True),
        (True, True, False),
        (False, True, True),
    ],
    ids=["enforce_poll", "poll", "auto_push", "auto_poll"],
)
async def test_enforce_polling(
    hass: HomeAssistant,
    mock_imap_protocol: MagicMock,
    enable_push: bool,
    should_poll: True,
) -> None:
    """Test enforce polling."""
    event_called = async_capture_events(hass, "imap_content")
    config = MOCK_CONFIG.copy()
    config["enable_push"] = enable_push

    config_entry = MockConfigEntry(domain=DOMAIN, data=config)
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
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT

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

    if should_poll:
        mock_imap_protocol.wait_server_push.assert_not_called()
    else:
        mock_imap_protocol.assert_has_calls([call.wait_server_push])
