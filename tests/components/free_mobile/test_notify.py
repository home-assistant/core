"""Test Free Mobile notify platform."""

from http import HTTPStatus
from unittest.mock import MagicMock

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.core import HomeAssistant

from .conftest import CONF_INPUT

from tests.common import MockConfigEntry


async def test_entity_send_message_success(
    hass: HomeAssistant, mock_freesms: MagicMock
) -> None:
    """Test successful SMS sending through the notify entity."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.OK
    mock_freesms.send_sms.return_value.ok = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "Test message", "entity_id": "notify.free_mobile"},
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once_with("Test message")


async def test_entity_send_message_400_bad_request(
    hass: HomeAssistant, mock_freesms: MagicMock
) -> None:
    """Test entity handles 400 Bad Request error."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.BAD_REQUEST

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "Test message", "entity_id": "notify.free_mobile"},
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once()


async def test_entity_send_message_403_forbidden(
    hass: HomeAssistant, mock_freesms: MagicMock
) -> None:
    """Test entity handles 403 Forbidden error (invalid credentials)."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.FORBIDDEN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "Test message", "entity_id": "notify.free_mobile"},
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once()


async def test_entity_send_message_429_rate_limit(
    hass: HomeAssistant, mock_freesms: MagicMock
) -> None:
    """Test entity handles 429 Too Many Requests error."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.TOO_MANY_REQUESTS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "Test message", "entity_id": "notify.free_mobile"},
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once()


async def test_entity_send_message_500_server_error(
    hass: HomeAssistant, mock_freesms: MagicMock
) -> None:
    """Test entity handles 500 Internal Server Error."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {ATTR_MESSAGE: "Test message", "entity_id": "notify.free_mobile"},
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once()


async def test_entity_unload(hass: HomeAssistant, mock_freesms: MagicMock) -> None:
    """Test entity is properly unloaded."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.OK

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("notify.free_mobile")
    assert state is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # After unload, entity should be unavailable or removed
    state = hass.states.get("notify.free_mobile")
    assert state is None or state.state == "unavailable"


async def test_entity_with_title(hass: HomeAssistant, mock_freesms: MagicMock) -> None:
    """Test entity sends message with title."""
    mock_freesms.send_sms.return_value.status_code = HTTPStatus.OK
    mock_freesms.send_sms.return_value.ok = True

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_INPUT,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "Hello World",
            "title": "My Title",
            "entity_id": "notify.free_mobile",
        },
    )
    await hass.async_block_till_done()

    mock_freesms.send_sms.assert_called_once_with("Hello World")
