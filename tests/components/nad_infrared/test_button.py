"""Tests for the NAD Infrared button platform."""

from infrared_protocols.codes.nad.amplifier import NADAmplifierCode
from infrared_protocols.codes.nad.cd import NADCDCode
from infrared_protocols.codes.nad.tape import NADTapeCode
from infrared_protocols.codes.nad.tuner import NADTunerCode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.nad_infrared.const import NADDeviceType
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared.common import MockInfraredEmitterEntity


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.BUTTON]


@pytest.mark.parametrize("device_type", list(NADDeviceType), indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all button entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device_by_identifier(
        ("nad_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
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
        ("button.nad_receiver_cursor_up", NADAmplifierCode.CURSOR_UP),
        ("button.nad_receiver_a_v_preset_1", NADAmplifierCode.AV_PRESET_1),
        ("button.nad_receiver_speaker_b", NADAmplifierCode.SPEAKER_B),
        ("button.nad_receiver_subwoofer_volume_up", NADAmplifierCode.SUB_VOLUME_UP),
        ("button.nad_receiver_menu", NADAmplifierCode.MENU),
        ("button.nad_receiver_test_tone", NADAmplifierCode.TEST),
        ("button.nad_receiver_source_up", NADAmplifierCode.SOURCE_UP),
        ("button.nad_receiver_source_down", NADAmplifierCode.SOURCE_DOWN),
        ("button.nad_receiver_delete_preset", NADTunerCode.DELETE),
    ],
)
@pytest.mark.parametrize("device_type", [NADDeviceType.RECEIVER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: NADAmplifierCode | NADTunerCode | NADCDCode | NADTapeCode,
) -> None:
    """Test pressing a button sends the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.usefixtures("init_integration")
async def test_button_availability_follows_ir_entity(hass: HomeAssistant) -> None:
    """Test button becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass, "button.nad_receiver_display", [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )


@pytest.mark.parametrize(
    ("device_type", "entity_id", "expected_code"),
    [
        (
            NADDeviceType.CD_PLAYER,
            "button.nad_cd_player_open_close",
            NADCDCode.OPEN_CLOSE,
        ),
        (NADDeviceType.TUNER, "button.nad_tuner_fm", NADTunerCode.FM),
        (
            NADDeviceType.TUNER,
            "button.nad_tuner_preset_up",
            NADTunerCode.PRESET_UP,
        ),
        (
            NADDeviceType.AMPLIFIER,
            "button.nad_amplifier_speaker_a",
            NADAmplifierCode.SPEAKER_A,
        ),
        (
            NADDeviceType.TAPE_DECK,
            "button.nad_cassette_deck_deck_a_play",
            NADTapeCode.DECK_A_PLAY,
        ),
        (
            NADDeviceType.TAPE_DECK,
            "button.nad_cassette_deck_deck_b_rewind",
            NADTapeCode.DECK_B_REWIND,
        ),
    ],
    indirect=["device_type"],
)
@pytest.mark.usefixtures("init_integration")
async def test_other_device_button_press_sends_correct_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_id: str,
    expected_code: NADAmplifierCode | NADTunerCode | NADCDCode | NADTapeCode,
) -> None:
    """Test buttons of the other device types send the correct IR code."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [expected_code]


@pytest.mark.parametrize(
    ("device_type", "has_amplifier_buttons", "has_tuner_buttons"),
    [
        (NADDeviceType.RECEIVER, True, True),
        (NADDeviceType.AMPLIFIER, True, False),
        (NADDeviceType.TUNER, False, True),
    ],
    indirect=["device_type"],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_combines_amplifier_and_tuner(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    has_amplifier_buttons: bool,
    has_tuner_buttons: bool,
) -> None:
    """A receiver gets both the amplifier and the tuner buttons."""
    keys = {
        entry.translation_key
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert ("speaker_a" in keys) is has_amplifier_buttons
    assert ("tuner_fm" in keys) is has_tuner_buttons


@pytest.mark.parametrize("device_type", [NADDeviceType.TUNER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_tuner_number_buttons_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The tuner number keys are created but disabled by default."""
    entry = entity_registry.async_get("button.nad_tuner_number_1")
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("button.nad_tuner_number_1") is None


@pytest.mark.parametrize("device_type", [NADDeviceType.CD_PLAYER], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_cd_changer_buttons_disabled_by_default(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The disc keys only work on CD changers, so they start disabled."""
    for entity_id in ("button.nad_cd_player_disc_1", "button.nad_cd_player_next_disc"):
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None
