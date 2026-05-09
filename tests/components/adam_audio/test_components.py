"""Tests for ADAM Audio platform components (switch, number, select)."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.adam_audio.const import DOMAIN
from homeassistant.components.adam_audio.data import AdamAudioIntegrationData
from homeassistant.components.adam_audio.entity import (
    AdamAudioEntity,
    AdamAudioGroupEntity,
)
from homeassistant.components.adam_audio.number import (
    _NUMBER_DESCRIPTORS,
    AdamAudioGroupNumber,
    AdamAudioNumber,
)
from homeassistant.components.adam_audio.select import (
    AdamAudioGroupInputSelect,
    AdamAudioGroupVoicingSelect,
)
from homeassistant.components.adam_audio.switch import (
    AdamAudioGroupMuteSwitch,
    AdamAudioGroupSleepSwitch,
)
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.components.select import ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test switch entities."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Mute switch
    mute_entity = "switch.left_speaker_mute"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: mute_entity},
        blocking=True,
    )
    mock_client.async_set_mute.assert_called_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: mute_entity},
        blocking=True,
    )
    mock_client.async_set_mute.assert_called_with(False)

    # Standby switch
    standby_entity = "switch.left_speaker_sleep"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: standby_entity},
        blocking=True,
    )
    mock_client.async_set_sleep.assert_called_once_with(True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: standby_entity},
        blocking=True,
    )
    mock_client.async_set_sleep.assert_called_with(False)


async def test_number_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test number entities."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    bass_entity = "number.left_speaker_bass"
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: bass_entity, ATTR_VALUE: 1.0},
        blocking=True,
    )
    mock_client.async_set_bass.assert_called_once_with(1)

    desk_entity = "number.left_speaker_desk"
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: desk_entity, ATTR_VALUE: -1.0},
        blocking=True,
    )
    mock_client.async_set_desk.assert_called_once_with(-1)

    presence_entity = "number.left_speaker_presence"
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: presence_entity, ATTR_VALUE: 1.0},
        blocking=True,
    )
    mock_client.async_set_presence.assert_called_once_with(1)

    treble_entity = "number.left_speaker_treble"
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: treble_entity, ATTR_VALUE: 0.0},
        blocking=True,
    )
    mock_client.async_set_treble.assert_called_once_with(0)


async def test_select_entities(
    hass: HomeAssistant,
    mock_config_entry,
    mock_client: MagicMock,
) -> None:
    """Test select entities."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    voicing_entity = "select.left_speaker_voicing"
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: voicing_entity, ATTR_OPTION: "Pure"},
        blocking=True,
    )
    mock_client.async_set_voicing.assert_called_once_with(0)

    input_entity = "select.left_speaker_input_source"
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: input_entity, ATTR_OPTION: "RCA"},
        blocking=True,
    )
    mock_client.async_set_input.assert_called_once_with(0)


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_switch_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group switch entities control all speakers."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mute_entity = "switch.all_speakers_mute"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: mute_entity},
        blocking=True,
    )
    mock_client.async_set_mute.assert_called_with(True)

    sleep_entity = "switch.all_speakers_sleep"
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: sleep_entity},
        blocking=True,
    )
    mock_client.async_set_sleep.assert_called_with(True)


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_number_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group number entities."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    bass_entity = "number.all_speakers_bass"
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: bass_entity, ATTR_VALUE: 1.0},
        blocking=True,
    )
    mock_client.async_set_bass.assert_called_with(1)


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_select_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group select entities."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    voicing_entity = "select.all_speakers_voicing"
    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: voicing_entity, ATTR_OPTION: "Pure"},
        blocking=True,
    )
    mock_client.async_set_voicing.assert_called_with(0)


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_switch_turn_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group switch turn_off controls all speakers."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.all_speakers_mute"},
        blocking=True,
    )
    mock_client.async_set_mute.assert_called_with(False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.all_speakers_sleep"},
        blocking=True,
    )
    mock_client.async_set_sleep.assert_called_with(False)


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_select_input(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group input select controls all speakers."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.all_speakers_input_source", ATTR_OPTION: "RCA"},
        blocking=True,
    )
    mock_client.async_set_input.assert_called_with(0)


async def test_group_switch_no_coordinators(hass: HomeAssistant) -> None:
    """Test group switch returns False when no coordinators are loaded."""
    assert AdamAudioGroupMuteSwitch(hass).is_on is False
    assert AdamAudioGroupSleepSwitch(hass).is_on is False


async def test_group_select_no_coordinators(hass: HomeAssistant) -> None:
    """Test group selects return defaults when no coordinators are loaded."""
    assert AdamAudioGroupInputSelect(hass).current_option == "RCA"
    assert AdamAudioGroupVoicingSelect(hass).current_option == "Pure"


async def test_group_number_no_coordinators(hass: HomeAssistant) -> None:
    """Test group number returns min value when no coordinators are loaded."""
    num = AdamAudioGroupNumber(hass, _NUMBER_DESCRIPTORS[0])
    assert num.native_value == _NUMBER_DESCRIPTORS[0].native_min


def test_number_unavailable_parent() -> None:
    """Test per-device number returns unavailable when parent is unavailable."""
    entity = object.__new__(AdamAudioNumber)
    entity._desc = _NUMBER_DESCRIPTORS[0]

    with patch.object(
        AdamAudioEntity, "available", new_callable=PropertyMock, return_value=False
    ):
        assert entity.available is False


def test_number_available_null_voicings() -> None:
    """Test per-device number available when valid_voicings is None."""
    entity = object.__new__(AdamAudioNumber)
    entity._desc = replace(_NUMBER_DESCRIPTORS[0], valid_voicings=None)

    with patch.object(
        AdamAudioEntity, "available", new_callable=PropertyMock, return_value=True
    ):
        assert entity.available is True


def test_group_number_unavailable_parent() -> None:
    """Test group number returns unavailable when parent is unavailable."""
    entity = object.__new__(AdamAudioGroupNumber)
    entity._desc = _NUMBER_DESCRIPTORS[0]

    with patch.object(
        AdamAudioGroupEntity, "available", new_callable=PropertyMock, return_value=False
    ):
        assert entity.available is False


def test_group_number_available_null_voicings() -> None:
    """Test group number available when valid_voicings is None."""
    entity = object.__new__(AdamAudioGroupNumber)
    entity._desc = replace(_NUMBER_DESCRIPTORS[0], valid_voicings=None)

    with patch.object(
        AdamAudioGroupEntity, "available", new_callable=PropertyMock, return_value=True
    ):
        assert entity.available is True


@pytest.mark.usefixtures("mock_config_entry", "mock_client")
async def test_group_resubscribes_new_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Test group entities re-subscribe when a new coordinator appears."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.adam_audio.coordinator.AdamAudioClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Inject a second coordinator
    mock_coord2 = MagicMock()
    mock_coord2.client.state = mock_client.state
    mock_coord2.client.available = True
    mock_coord2.client.async_set_mute = AsyncMock()
    mock_coord2.async_add_listener = MagicMock(return_value=lambda: None)
    integration_data: AdamAudioIntegrationData = hass.data[DOMAIN]
    integration_data.coordinators["fake_entry_2"] = mock_coord2

    # Group turn_on triggers async_write_ha_state -> detects count mismatch -> re-subscribes
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.all_speakers_mute"},
        blocking=True,
    )
    mock_client.async_set_mute.assert_called_with(True)
    mock_coord2.client.async_set_mute.assert_called_with(True)

    del integration_data.coordinators["fake_entry_2"]
