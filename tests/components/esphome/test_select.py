"""Test ESPHome selects."""

from unittest.mock import call

from aioesphomeapi import APIClient, SelectInfo, SelectState, VoiceAssistantFeature
import pytest

from homeassistant.components.assist_satellite import (
    AssistSatelliteConfiguration,
    AssistSatelliteWakeWord,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .common import get_satellite_entity
from .conftest import MockESPHomeDeviceType, MockGenericDeviceEntryType


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_pipeline_selector(
    hass: HomeAssistant,
) -> None:
    """Test assist pipeline selector."""

    state = hass.states.get("select.test_assistant")
    assert state is not None
    assert state.state == "preferred"


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_vad_sensitivity_select(
    hass: HomeAssistant,
) -> None:
    """Test VAD sensitivity select.

    Functionality is tested in assist_pipeline/test_select.py.
    This test is only to ensure it is set up.
    """
    state = hass.states.get("select.test_finished_speaking_detection")
    assert state is not None
    assert state.state == "default"


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_wake_word_select(
    hass: HomeAssistant,
) -> None:
    """Test that wake word select is unavailable initially."""
    state = hass.states.get("select.test_wake_word")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_select_generic_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic select entity."""
    entity_info = [
        SelectInfo(
            object_id="myselect",
            key=1,
            name="my select",
            unique_id="my_select",
            options=["a", "b"],
        )
    ]
    states = [SelectState(key=1, state="a")]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("select.test_myselect")
    assert state is not None
    assert state.state == "a"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_myselect", ATTR_OPTION: "b"},
        blocking=True,
    )
    mock_client.select_command.assert_has_calls([call(1, "b")])


async def test_wake_word_select_no_wake_words(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test wake word select is unavailable when there are no available wake word."""
    device_config = AssistSatelliteConfiguration(
        available_wake_words=[],
        active_wake_words=[],
        max_active_wake_words=1,
    )
    mock_client.get_voice_assistant_configuration.return_value = device_config

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert not satellite.async_get_configuration().available_wake_words

    # Select should be unavailable
    state = hass.states.get("select.test_wake_word")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_wake_word_select_zero_max_wake_words(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test wake word select is unavailable max wake words is zero."""
    device_config = AssistSatelliteConfiguration(
        available_wake_words=[
            AssistSatelliteWakeWord("okay_nabu", "Okay Nabu", ["en"]),
        ],
        active_wake_words=[],
        max_active_wake_words=0,
    )
    mock_client.get_voice_assistant_configuration.return_value = device_config

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert satellite.async_get_configuration().max_active_wake_words == 0

    # Select should be unavailable
    state = hass.states.get("select.test_wake_word")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_wake_word_select_no_active_wake_words(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test wake word select uses first available wake word if none are active."""
    device_config = AssistSatelliteConfiguration(
        available_wake_words=[
            AssistSatelliteWakeWord("okay_nabu", "Okay Nabu", ["en"]),
            AssistSatelliteWakeWord("hey_jarvis", "Hey Jarvis", ["en"]),
        ],
        active_wake_words=[],
        max_active_wake_words=1,
    )
    mock_client.get_voice_assistant_configuration.return_value = device_config

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert not satellite.async_get_configuration().active_wake_words

    # First available wake word should be selected
    state = hass.states.get("select.test_wake_word")
    assert state is not None
    assert state.state == "Okay Nabu"
