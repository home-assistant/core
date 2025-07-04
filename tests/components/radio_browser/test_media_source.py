"""Test the Radio Browser media source."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from radios import RadioBrowser

from homeassistant.components.media_source import MediaSourceItem, Unresolvable
from homeassistant.components.radio_browser.const import DOMAIN
from homeassistant.components.radio_browser.media_source import (
    RadioMediaSource,
    async_get_media_source,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_radio_browser() -> AsyncMock:
    """Mock RadioBrowser."""
    radio_browser = AsyncMock(spec=RadioBrowser)
    # Mock station without full Station object to avoid constructor complexity
    mock_station = AsyncMock()
    mock_station.uuid = "test-uuid"
    mock_station.name = "Test Station"
    mock_station.url = "https://example.com/stream"
    mock_station.codec = "MP3"
    mock_station.favicon = "https://example.com/favicon.ico"
    radio_browser.station.return_value = mock_station
    return radio_browser


async def test_media_source_without_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test media source raises error when runtime_data is missing."""
    mock_config_entry.add_to_hass(hass)

    # Don't set runtime_data to simulate the error condition
    media_source = RadioMediaSource(hass, mock_config_entry)

    with pytest.raises(
        Unresolvable, match="Radio Browser integration not properly loaded"
    ):
        _ = media_source.radios


async def test_media_source_with_none_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test media source raises error when runtime_data is None."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = None

    media_source = RadioMediaSource(hass, mock_config_entry)

    with pytest.raises(
        Unresolvable, match="Radio Browser integration not properly loaded"
    ):
        _ = media_source.radios


async def test_media_source_with_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_radio_browser: AsyncMock,
) -> None:
    """Test media source works correctly with runtime_data."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_radio_browser

    media_source = RadioMediaSource(hass, mock_config_entry)

    # Should not raise an error
    radios = media_source.radios
    assert radios is mock_radio_browser


async def test_async_get_media_source(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_radio_browser: AsyncMock,
) -> None:
    """Test async_get_media_source function."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = mock_radio_browser

    media_source = await async_get_media_source(hass)

    assert isinstance(media_source, RadioMediaSource)
    assert media_source.entry is mock_config_entry
    assert media_source.radios is mock_radio_browser


async def test_async_resolve_media_with_missing_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_resolve_media raises error when runtime_data is missing."""

    mock_config_entry.add_to_hass(hass)
    # Don't set runtime_data to simulate the error condition

    media_source = RadioMediaSource(hass, mock_config_entry)
    item = MediaSourceItem(
        hass=hass,
        domain=DOMAIN,
        identifier="test-uuid",
        target_media_player=None,
    )

    with pytest.raises(
        Unresolvable, match="Radio Browser integration not properly loaded"
    ):
        await media_source.async_resolve_media(item)


async def test_async_browse_media_with_missing_runtime_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_browse_media raises error when runtime_data is missing."""

    mock_config_entry.add_to_hass(hass)
    # Don't set runtime_data to simulate the error condition

    media_source = RadioMediaSource(hass, mock_config_entry)
    item = MediaSourceItem(
        hass=hass,
        domain=DOMAIN,
        identifier="",
        target_media_player=None,
    )

    with pytest.raises(
        Unresolvable, match="Radio Browser integration not properly loaded"
    ):
        await media_source.async_browse_media(item)
