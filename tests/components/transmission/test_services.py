"""Tests for the Transmission services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.transmission.const import (
    ATTR_DELETE_DATA,
    ATTR_DOWNLOAD_PATH,
    ATTR_LABELS,
    ATTR_TORRENT,
    ATTR_TORRENT_FILTER,
    ATTR_TORRENTS,
    CONF_ENTRY_ID,
    DOMAIN,
    SERVICE_ADD_TORRENT,
    SERVICE_GET_TORRENTS,
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

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            {
                CONF_ENTRY_ID: mock_config_entry.entry_id,
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_not_found"


async def test_service_integration_not_found(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test service call with non-existent config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_TORRENT,
            {
                CONF_ENTRY_ID: "non_existent_entry_id",
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"


@pytest.mark.parametrize(
    ("payload", "expected_torrent", "kwargs"),
    [
        (
            {ATTR_TORRENT: "magnet:?xt=urn:btih:test", ATTR_LABELS: "Notify"},
            "magnet:?xt=urn:btih:test",
            {
                "labels": ["Notify"],
                "download_dir": None,
            },
        ),
        (
            {
                ATTR_TORRENT: "magnet:?xt=urn:btih:test",
                ATTR_LABELS: "Movies,Notify",
                ATTR_DOWNLOAD_PATH: "/custom/path",
            },
            "magnet:?xt=urn:btih:test",
            {
                "labels": ["Movies", "Notify"],
                "download_dir": "/custom/path",
            },
        ),
        (
            {ATTR_TORRENT: "http://example.com/test.torrent"},
            "http://example.com/test.torrent",
            {
                "labels": None,
                "download_dir": None,
            },
        ),
        (
            {ATTR_TORRENT: "ftp://example.com/test.torrent"},
            "ftp://example.com/test.torrent",
            {
                "labels": None,
                "download_dir": None,
            },
        ),
        (
            {ATTR_TORRENT: "/config/test.torrent"},
            "/config/test.torrent",
            {
                "labels": None,
                "download_dir": None,
            },
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


@pytest.mark.parametrize(
    ("filter_mode", "expected_statuses", "expected_torrents"),
    [
        ("all", ["seeding", "downloading", "stopped"], [1, 2, 3]),
        ("started", ["downloading"], [1]),
        ("completed", ["seeding"], [2]),
        ("paused", ["stopped"], [3]),
        ("active", ["seeding", "downloading"], [1, 2]),
    ],
)
async def test_get_torrents_service(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_torrent,
    filter_mode: str,
    expected_statuses: list[str],
    expected_torrents: list[int],
) -> None:
    """Test get torrents service with various filter modes."""
    client = mock_transmission_client.return_value

    downloading_torrent = mock_torrent(torrent_id=1, name="Downloading", status=4)
    seeding_torrent = mock_torrent(torrent_id=2, name="Seeding", status=6)
    stopped_torrent = mock_torrent(torrent_id=3, name="Stopped", status=0)

    client.get_torrents.return_value = [
        downloading_torrent,
        seeding_torrent,
        stopped_torrent,
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_TORRENTS,
        {
            CONF_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_TORRENT_FILTER: filter_mode,
        },
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert ATTR_TORRENTS in response
    torrents = response[ATTR_TORRENTS]
    assert isinstance(torrents, dict)

    assert len(torrents) == len(expected_statuses)

    for torrent_name, torrent_data in torrents.items():
        assert isinstance(torrent_data, dict)
        assert "id" in torrent_data
        assert "name" in torrent_data
        assert "status" in torrent_data
        assert torrent_data["name"] == torrent_name
        assert torrent_data["id"] in expected_torrents
        expected_torrents.remove(int(torrent_data["id"]))

    assert len(expected_torrents) == 0
