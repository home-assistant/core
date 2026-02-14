"""Tests for the Cambridge Audio select platform."""

from unittest.mock import AsyncMock, patch

from aiostreammagic.models import EQBand, UserEQ
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.cambridge_audio.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_setting_value(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting value."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.cambridge_audio_cxnv2_display_brightness",
            ATTR_OPTION: "dim",
        },
        blocking=True,
    )
    mock_stream_magic_client.set_display_brightness.assert_called_once_with("dim")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.cambridge_audio_cxnv2_audio_output",
            ATTR_OPTION: "Speaker A",
        },
        blocking=True,
    )
    mock_stream_magic_client.set_audio_output.assert_called_once_with("speaker_a")


async def test_equalizer_preset_setting(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting equalizer preset."""
    await setup_integration(hass, mock_config_entry)

    # Test setting bass_boost preset
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.cambridge_audio_cxnv2_equalizer_preset",
            ATTR_OPTION: "bass_boost",
        },
        blocking=True,
    )

    # Verify set_equalizer_params was called
    assert mock_stream_magic_client.set_equalizer_params.call_count == 1
    call_args = mock_stream_magic_client.set_equalizer_params.call_args[0][0]

    # Verify it's a UserEQ object with correct properties
    assert isinstance(call_args, UserEQ)
    assert call_args.enabled is True
    assert len(call_args.bands) == 7

    # Verify the gains match the bass_boost preset [3.0, 3.0, 1.0, 0.0, -1.0, -0.5, -0.3]
    expected_gains = [3.0, 3.0, 1.0, 0.0, -1.0, -0.5, -0.3]
    for i, band in enumerate(call_args.bands):
        assert isinstance(band, EQBand)
        assert band.index == i
        assert band.gain == expected_gains[i]

    mock_stream_magic_client.set_equalizer_params.reset_mock()

    # Test setting another preset (movie)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.cambridge_audio_cxnv2_equalizer_preset",
            ATTR_OPTION: "movie",
        },
        blocking=True,
    )

    assert mock_stream_magic_client.set_equalizer_params.call_count == 1
    call_args = mock_stream_magic_client.set_equalizer_params.call_args[0][0]

    # Verify the gains match the movie preset [0.0, 1.4, -0.4, -2.0, -0.6, 0.6, 1.1]
    expected_gains = [0.0, 1.4, -0.4, -2.0, -0.6, 0.6, 1.1]
    for i, band in enumerate(call_args.bands):
        assert band.gain == expected_gains[i]


async def test_equalizer_preset_custom_ignored(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that selecting custom preset does nothing."""
    await setup_integration(hass, mock_config_entry)

    # Try to set custom preset
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.cambridge_audio_cxnv2_equalizer_preset",
            ATTR_OPTION: "custom",
        },
        blocking=True,
    )

    # Verify set_equalizer_params was NOT called (custom is read-only)
    mock_stream_magic_client.set_equalizer_params.assert_not_called()
