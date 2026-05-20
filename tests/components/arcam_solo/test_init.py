"""Tests for the Arcam Solo integration init module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.arcam_solo import async_setup_entry, async_unload_entry
from homeassistant.components.arcam_solo.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test setting up a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0"},
    )

    with (
        patch("homeassistant.components.arcam_solo.ArcamSolo") as mock_arcam_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(),
        ) as mock_forward,
    ):
        mock_arcam = mock_arcam_cls.return_value
        mock_arcam.connect = AsyncMock()

        assert await async_setup_entry(hass, entry) is True

    mock_arcam_cls.assert_called_once_with(uri="/dev/ttyUSB0")
    mock_arcam.connect.assert_awaited_once()
    mock_forward.assert_awaited_once()
    assert entry.runtime_data is mock_arcam


@pytest.mark.parametrize("exception", [TimeoutError, OSError])
async def test_async_setup_entry_not_ready(
    hass: HomeAssistant, exception: type[Exception]
) -> None:
    """Test setup raises ConfigEntryNotReady on connection errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyUSB0"},
    )

    with patch("homeassistant.components.arcam_solo.ArcamSolo") as mock_arcam_cls:
        mock_arcam_cls.return_value.connect = AsyncMock(side_effect=exception)
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)


async def test_async_unload_entry_success_disconnects(hass: HomeAssistant) -> None:
    """Test unloading a config entry calls disconnect."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyUSB0"})
    entry.runtime_data = MagicMock()
    entry.runtime_data.disconnect = AsyncMock()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry) is True

    entry.runtime_data.disconnect.assert_awaited_once()


async def test_async_unload_entry_failure_skips_disconnect(hass: HomeAssistant) -> None:
    """Test unloading failure does not call disconnect."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyUSB0"})
    entry.runtime_data = MagicMock()
    entry.runtime_data.disconnect = AsyncMock()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert await async_unload_entry(hass, entry) is False

    entry.runtime_data.disconnect.assert_not_awaited()
