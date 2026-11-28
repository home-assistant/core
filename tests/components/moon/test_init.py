"""Tests for the Moon integration."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.moon.helpers import (
    EPHEMERIS_FILE,
    EPHEMERIS_URL,
    MoonData,
    _async_download_ephemeris,
    async_get_moon_data,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    moon_data: MoonData,
) -> None:
    """Test the Moon configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_ephemeris_closed_on_stop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    moon_data: MoonData,
) -> None:
    """Test the shared ephemeris is closed when Home Assistant stops."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire_internal(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    moon_data.ephemeris.close.assert_called_once()


async def test_setup_retries_when_ephemeris_download_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry is retried when the ephemeris cannot be downloaded."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.moon.helpers._async_download_ephemeris",
        side_effect=OSError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_download_writes_ephemeris(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, tmp_path: Path
) -> None:
    """Test the ephemeris is written to the cache directory on success."""
    aioclient_mock.get(EPHEMERIS_URL, content=b"ephemeris")
    path = tmp_path / EPHEMERIS_FILE

    await _async_download_ephemeris(hass, str(path))

    assert path.read_bytes() == b"ephemeris"
    assert not path.with_name(f"{EPHEMERIS_FILE}.tmp").exists()


@pytest.mark.parametrize(
    "response",
    [
        pytest.param({"status": 500}, id="http-error"),
        pytest.param({"exc": TimeoutError}, id="timeout"),
    ],
)
async def test_download_failure_raises_oserror(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    tmp_path: Path,
    response: dict[str, Any],
) -> None:
    """Test a failed download raises OSError and leaves no ephemeris behind."""
    aioclient_mock.get(EPHEMERIS_URL, **response)
    path = tmp_path / EPHEMERIS_FILE

    with pytest.raises(OSError):
        await _async_download_ephemeris(hass, str(path))

    assert not path.exists()


async def test_corrupt_ephemeris_is_downloaded_again(
    hass: HomeAssistant, moon_data: MoonData, tmp_path: Path
) -> None:
    """Test an unreadable cached ephemeris is removed and downloaded again."""
    path = tmp_path / EPHEMERIS_FILE
    path.write_bytes(b"corrupt")

    with (
        patch.object(hass.config, "cache_path", return_value=str(tmp_path)),
        patch(
            "homeassistant.components.moon.helpers._load_moon_data",
            side_effect=[ValueError, moon_data],
        ),
        patch(
            "homeassistant.components.moon.helpers._async_download_ephemeris"
        ) as download,
    ):
        assert await async_get_moon_data(hass) is moon_data

    download.assert_awaited_once()
    assert not path.exists()


async def test_unreadable_ephemeris_after_download_raises_oserror(
    hass: HomeAssistant,
) -> None:
    """Test a freshly downloaded ephemeris that cannot be read raises OSError."""
    with (
        patch(
            "homeassistant.components.moon.helpers._load_moon_data",
            side_effect=ValueError,
        ),
        patch("homeassistant.components.moon.helpers._async_download_ephemeris"),
        pytest.raises(OSError),
    ):
        await async_get_moon_data(hass)
