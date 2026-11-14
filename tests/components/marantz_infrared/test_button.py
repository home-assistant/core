"""Tests for the Marantz Infrared button platform."""

from infrared_protocols.codes.marantz.audio import MarantzAudioCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.const import CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MOCK_INFRARED_EMITTER_ENTITY_ID

BUTTON_ENTITY_ID_SPEAKER_AB = "button.marantz_pm6006_integrated_amplifier_speaker_a_b"
BUTTON_ENTITY_ID_SPEAKER_A_OFF = (
    "button.marantz_pm8006_integrated_amplifier_speaker_a_off"
)
BUTTON_ENTITY_ID_SPEAKER_A_ON = (
    "button.marantz_pm8006_integrated_amplifier_speaker_a_on"
)
BUTTON_ENTITY_ID_SPEAKER_B_OFF = (
    "button.marantz_pm8006_integrated_amplifier_speaker_b_off"
)
BUTTON_ENTITY_ID_SPEAKER_B_ON = (
    "button.marantz_pm8006_integrated_amplifier_speaker_b_on"
)
BUTTON_ENTITY_ID_SOURCE_DIRECT = (
    "button.marantz_pm6006_integrated_amplifier_source_direct"
)
BUTTON_ENTITY_ID_LOUDNESS = "button.marantz_pm6006_integrated_amplifier_loudness"
BUTTON_ENTITY_ID_POWER_AMP_DIRECT_ON = (
    "button.marantz_pm8006_integrated_amplifier_power_amp_direct_on"
)
BUTTON_ENTITY_ID_POWER_AMP_DIRECT_OFF = (
    "button.marantz_pm8006_integrated_amplifier_power_amp_direct_off"
)


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

    device_entry = device_registry.async_get_device_by_identifier(
        ("marantz_infrared", mock_config_entry.entry_id), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    ("model", "entity_id", "expected_code"),
    [
        (
            "pm6006_integrated_amplifier",
            BUTTON_ENTITY_ID_SPEAKER_AB,
            MarantzAudioCode.SPEAKER_AB,
        ),
        (
            "pm6006_integrated_amplifier",
            BUTTON_ENTITY_ID_SOURCE_DIRECT,
            MarantzAudioCode.SOURCE_DIRECT,
        ),
        (
            "pm6006_integrated_amplifier",
            BUTTON_ENTITY_ID_LOUDNESS,
            MarantzAudioCode.LOUDNESS,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_SPEAKER_A_OFF,
            MarantzAudioCode.SPEAKER_A_OFF,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_SPEAKER_A_ON,
            MarantzAudioCode.SPEAKER_A_ON,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_SPEAKER_B_OFF,
            MarantzAudioCode.SPEAKER_B_OFF,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_SPEAKER_B_ON,
            MarantzAudioCode.SPEAKER_B_ON,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_POWER_AMP_DIRECT_ON,
            MarantzAudioCode.POWER_AMP_DIRECT_ON,
        ),
        (
            "pm8006_integrated_amplifier",
            BUTTON_ENTITY_ID_POWER_AMP_DIRECT_OFF,
            MarantzAudioCode.POWER_AMP_DIRECT_OFF,
        ),
    ],
    indirect=["model"],
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
        ButtonService.PRESS,
        {CommonServiceArgument.ENTITY_ID: entity_id},
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
        hass, BUTTON_ENTITY_ID_LOUDNESS, [MOCK_INFRARED_EMITTER_ENTITY_ID]
    )
