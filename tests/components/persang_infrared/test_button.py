"""Tests for the Persang Infrared button platform."""

from infrared_protocols.codes.persang.speaker import PersangSpeakerCode
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

BUTTON_ENTITY_ID_MODE = "button.persang_speaker_mode"


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
    """Test all button entities are created with the correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("persang_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
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
        ("button.persang_speaker_mode", PersangSpeakerCode.MODE),
        ("button.persang_speaker_equalizer", PersangSpeakerCode.EQ),
        ("button.persang_speaker_scan", PersangSpeakerCode.SCAN),
        ("button.persang_speaker_repeat", PersangSpeakerCode.REPEAT),
        ("button.persang_speaker_number_0", PersangSpeakerCode.NUM_0),
        ("button.persang_speaker_number_1", PersangSpeakerCode.NUM_1),
        ("button.persang_speaker_number_2", PersangSpeakerCode.NUM_2),
        ("button.persang_speaker_number_3", PersangSpeakerCode.NUM_3),
        ("button.persang_speaker_number_4", PersangSpeakerCode.NUM_4),
        ("button.persang_speaker_number_5", PersangSpeakerCode.NUM_5),
        ("button.persang_speaker_number_6", PersangSpeakerCode.NUM_6),
        ("button.persang_speaker_number_7", PersangSpeakerCode.NUM_7),
        ("button.persang_speaker_number_8", PersangSpeakerCode.NUM_8),
        ("button.persang_speaker_number_9", PersangSpeakerCode.NUM_9),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: PersangSpeakerCode,
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


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test a button becomes unavailable when the IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, BUTTON_ENTITY_ID_MODE, MOCK_INFRARED_EMITTER_ENTITY_ID
    )
