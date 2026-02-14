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


async def test_equalizer_preset_without_user_eq(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that equalizer preset entity is not created when user_eq is None."""
    # Set user_eq to None to simulate a device without EQ support
    mock_stream_magic_client.audio.user_eq = None

    await setup_integration(hass, mock_config_entry)

    # Verify the equalizer preset entity was not created
    assert (
        entity_registry.async_get("select.cambridge_audio_cxnv2_equalizer_preset")
        is None
    )

    # Verify other select entities still exist
    assert (
        entity_registry.async_get("select.cambridge_audio_cxnv2_display_brightness")
        is not None
    )
    assert (
        entity_registry.async_get("select.cambridge_audio_cxnv2_audio_output")
        is not None
    )


async def test_equalizer_preset_custom_detection(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test detection of custom EQ settings that don't match any preset."""
    # Modify the bands to have custom gains that don't match any preset
    custom_bands = [
        EQBand(index=0, gain=1.5),
        EQBand(index=1, gain=2.0),
        EQBand(index=2, gain=-1.5),
        EQBand(index=3, gain=0.5),
        EQBand(index=4, gain=-0.5),
        EQBand(index=5, gain=1.0),
        EQBand(index=6, gain=-1.0),
    ]
    mock_stream_magic_client.audio.user_eq.bands = custom_bands

    await setup_integration(hass, mock_config_entry)

    # Verify the entity shows "custom" since gains don't match any preset
    state = hass.states.get("select.cambridge_audio_cxnv2_equalizer_preset")
    assert state is not None
    assert state.state == "custom"


async def test_equalizer_preset_empty_bands(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test handling of empty bands list."""
    # Set bands to empty list
    mock_stream_magic_client.audio.user_eq.bands = []

    await setup_integration(hass, mock_config_entry)

    # Verify the entity exists but has no state (or unknown state)
    state = hass.states.get("select.cambridge_audio_cxnv2_equalizer_preset")
    assert state is not None
    assert state.state == "unknown"
