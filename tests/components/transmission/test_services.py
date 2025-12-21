"""Tests for the Transmission services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.transmission.const import (
    ATTR_DELETE_DATA,
    ATTR_DOWNLOAD_PATH,
    ATTR_TORRENT,
    CONF_ENTRY_ID,
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_REMOVE_TORRENT,
    SERVICE_START_TORRENT,
    SERVICE_STOP_TORRENT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_service_config_entry_not_loaded_state(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call when config entry is in failed state."""
    mock_config_entry.add_to_hass(hass)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    with pytest.raises(ServiceValidationError, match="service_not_found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            {
                CONF_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
            },
            blocking=True,
        )


async def test_service_integration_not_found(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call with non-existent config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        ServiceValidationError, match='Integration "transmission" not found'
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            {
                CONF_ENTRY_ID: "non_existent_entry_id",
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("payload", "expected_torrent", "kwargs"),
    [
        (
            {ATTR_TORRENT: "magnet:?xt=urn:btih:test"},
            "magnet:?xt=urn:btih:test",
            {},
        ),
        (
            {
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
                ATTR_DOWNLOAD_PATH: "/custom/path",
            },
            "magnet:?xt=urn:btih:test",
            {"download_dir": "/custom/path"},
        ),
        (
            {ATTR_TORRENT: "http://example.com/test.torrent"},
            "http://example.com/test.torrent",
            {},
        ),
        (
            {ATTR_TORRENT: "ftp://example.com/test.torrent"},
            "ftp://example.com/test.torrent",
            {},
        ),
        (
            {ATTR_TORRENT: "/config/test.torrent"},
            "/config/test.torrent",
            {},
        ),
    ],
)
async def test_add_torrent_service_success(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    payload: dict[str, str],
    expected_torrent: str,
    kwargs: dict[str, str | None],
) -> None:
    """Test successful torrent addition with url and path sources."""
    client = mock_transmission_client.return_value
    client.add_torrent.return_value = MagicMock(id=123, name="test_torrent")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    full_service_data = {CONF_ENTRY_ID: mock_config_entry.entry_id} | payload

    with patch.object(hass.config, "is_allowed_path", return_value=True):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            full_service_data,
            blocking=True,
        )

    client.add_torrent.assert_called_once_with(expected_torrent, **kwargs)


async def test_add_torrent_service_invalid_path(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test torrent addition with invalid path."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="Could not add torrent"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            {
                CONF_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_TORRENT: "/etc/bad.torrent",
            },
            blocking=True,
        )


async def test_start_torrent_service_success(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful torrent start."""
    client = mock_transmission_client.return_value

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_TORRENT,
        {
            CONF_ENTRY_ID: mock_config_entry.entry_id,
            CONF_ID: 123,
        },
        blocking=True,
    )

    client.start_torrent.assert_called_once_with(123)


async def test_stop_torrent_service_success(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful torrent stop."""
    client = mock_transmission_client.return_value

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_STOP_TORRENT,
        {
            CONF_ENTRY_ID: mock_config_entry.entry_id,
            CONF_ID: 456,
        },
        blocking=True,
    )

    client.stop_torrent.assert_called_once_with(456)


async def test_remove_torrent_service_success(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful torrent removal without deleting data."""
    client = mock_transmission_client.return_value

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_TORRENT,
        {
            CONF_ENTRY_ID: mock_config_entry.entry_id,
            CONF_ID: 789,
        },
        blocking=True,
    )

    client.remove_torrent.assert_called_once_with(789, delete_data=False)


async def test_remove_torrent_service_with_delete_data(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful torrent removal with deleting data."""
    client = mock_transmission_client.return_value

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_TORRENT,
        {
            CONF_ENTRY_ID: mock_config_entry.entry_id,
            CONF_ID: 789,
            ATTR_DELETE_DATA: True,
        },
        blocking=True,
    )

    client.remove_torrent.assert_called_once_with(789, delete_data=True)
