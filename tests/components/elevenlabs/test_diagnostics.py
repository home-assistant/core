"""Test the ElevenLabs diagnostics."""

from unittest.mock import MagicMock

from elevenlabs.types import GetVoicesResponse, Voice
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.elevenlabs.const import CONF_VOICE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

VOICES = [
    Voice(voice_id="premade_voice_id", name="Rachel", category="premade"),
    Voice(voice_id="cloned_voice_id", name="Grandma Jane", category="cloned"),
    Voice(voice_id="generated_voice_id", name="My generated voice"),
]


@pytest.mark.parametrize(
    "voice_id",
    ["premade_voice_id", "cloned_voice_id", "missing_voice_id"],
    ids=["premade", "cloned", "missing"],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_async_client: MagicMock,
    mock_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    voice_id: str,
) -> None:
    """Test diagnostics."""
    mock_async_client.return_value.voices.get_all.return_value = GetVoicesResponse(
        voices=VOICES
    )
    mock_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_entry, options={**mock_entry.options, CONF_VOICE: voice_id}
    )
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)
        == snapshot
    )
