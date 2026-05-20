"""Tests for the Marantz Infrared button platform."""

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared.common import MockInfraredEmitterEntity

BUTTON_ENTITY_ID_SPEAKER_AB = "button.marantz_pm6006_integrated_amplifier_speaker_a_b"
BUTTON_ENTITY_ID_SOURCE_DIRECT = (
    "button.marantz_pm6006_integrated_amplifier_source_direct"
)
BUTTON_ENTITY_ID_LOUDNESS = "button.marantz_pm6006_integrated_amplifier_loudness"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all button entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(
        identifiers={("marantz_infrared", mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("entity_id", "expected_code"),
    [
        (BUTTON_ENTITY_ID_SPEAKER_AB, MarantzAudioCode.SPEAKER_AB),
        (BUTTON_ENTITY_ID_SOURCE_DIRECT, MarantzAudioCode.SOURCE_DIRECT),
        (BUTTON_ENTITY_ID_LOUDNESS, MarantzAudioCode.LOUDNESS),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: MarantzAudioCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    assert mock_infrared_emitter_entity.send_command_calls[0] == expected_code


@pytest.mark.parametrize(
    "model",
    ["sr_7300_receiver"],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_only_supported_buttons_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that only buttons for codes supported by the model are created."""
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    button_entries = [e for e in entity_entries if e.domain == "button"]
    assert len(button_entries) == 1
    assert button_entries[0].translation_key == "speaker_ab"


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, BUTTON_ENTITY_ID_LOUDNESS, MOCK_INFRARED_EMITTER_ENTITY_ID
    )
