"""Test the Blink init."""
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
import pytest

from homeassistant.components.blink.const import (
    DOMAIN,
    SERVICE_REFRESH,
    SERVICE_SAVE_VIDEO,
    SERVICE_SEND_PIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CAMERA_NAME = "Camera 1"
FILENAME = "blah"
PIN = "1234"


@pytest.mark.parametrize(
    ("the_error", "available"),
    [(ClientError, False), (TimeoutError, False), (None, False)],
)
async def test_setup_not_ready(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    the_error,
    available,
) -> None:
    """Test setup failed because we can't connect to the Blink system."""

    mock_blink_api.start = AsyncMock(side_effect=the_error)
    mock_blink_api.available = available

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_not_ready_authkey_required(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failed because 2FA is needed to connect to the Blink system."""

    mock_blink_auth_api.check_key_required = MagicMock(return_value=True)

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry_multiple(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test being able to unload one of 2 entries."""

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    hass.data[DOMAIN]["dummy"] = {1: 2}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_REFRESH)
    assert hass.services.has_service(DOMAIN, SERVICE_SAVE_VIDEO)
    assert hass.services.has_service(DOMAIN, SERVICE_SEND_PIN)


async def test_migrate_V0(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration script version 0."""

    mock_config_entry.version = 0

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(("version"), [1, 2])
async def test_migrate(
    hass: HomeAssistant,
    mock_blink_api: MagicMock,
    mock_blink_auth_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    version,
) -> None:
    """Test migration scripts."""

    mock_config_entry.version = version
    mock_config_entry.data = {**mock_config_entry.data, "login_response": "Blah"}

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
