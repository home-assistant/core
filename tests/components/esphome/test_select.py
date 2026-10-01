"""Test ESPHome selects."""

from unittest.mock import call

from aioesphomeapi import APIClient, SelectInfo, SelectState, VoiceAssistantFeature
import pytest

from homeassistant.components.assist_satellite import (
    AssistSatelliteConfiguration,
    AssistSatelliteWakeWord,
)
from homeassistant.components.esphome.const import (
    DOMAIN,
    NO_WAKE_WORD,
    VOICE_ASSISTANT_SELECT_KEYS,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import get_satellite_entity
from .conftest import (
    MockESPHomeDeviceType,
    MockGenericDeviceEntryType,
    reconnect_with_updated_entity_info,
)


async def test_voice_assistant_select_keys_match_the_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test VOICE_ASSISTANT_SELECT_KEYS names every select the platform builds."""
    device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )
    await hass.async_block_till_done()

    # The device offers no selects of its own, so these are the voice assistant's
    assert {
        entry.unique_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, device.entry.entry_id
        )
        if entry.domain == Platform.SELECT
    } == {
        f"{device.device_info.mac_address}-{key}" for key in VOICE_ASSISTANT_SELECT_KEYS
    }


async def test_selects_added_when_a_voice_assistant_appears(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the voice assistant selects are added when a device gains one.

    The device has a select of its own, so the platform is already set up when
    the voice assistant appears and is not forwarded a second time.
    """
    entity_info = [
        SelectInfo(object_id="myselect", key=1, name="my select", options=["a", "b"])
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[SelectState(key=1, state="a")],
        device_info={},
    )
    await hass.async_block_till_done()
    assert hass.states.get("select.test_my_select") is not None
    assert hass.states.get("select.test_assistant") is None

    await reconnect_with_updated_entity_info(
        hass,
        device,
        entity_info,
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )

    for entity_id in (
        "select.test_assistant",
        "select.test_assistant_2",
        "select.test_finished_speaking_detection",
        "select.test_wake_word",
        "select.test_wake_word_2",
    ):
        assert hass.states.get(entity_id) is not None, entity_id


async def test_selects_removed_when_the_platform_was_never_forwarded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test selects left by an earlier run go on a device that offers nothing.

    The select platform is only forwarded for a device that offers a voice
    assistant or has selects of its own, so a device with neither has nothing of
    this module running to remove what it left behind.
    """
    mac_address = "11:22:33:44:55:AA"
    for key in VOICE_ASSISTANT_SELECT_KEYS:
        entity_registry.async_get_or_create(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        )

    device = await mock_esphome_device(mock_client=mock_client, device_info={})
    await hass.async_block_till_done()

    # The device has no selects of its own either, so the platform really is
    # never forwarded and nothing in select.py runs for this entry
    assert Platform.SELECT not in device.entry.runtime_data.loaded_platforms

    for key in VOICE_ASSISTANT_SELECT_KEYS:
        assert not entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        ), key


async def test_selects_restored_when_a_voice_assistant_returns(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the selects come back when a device offers a voice assistant again."""
    entity_info = [
        SelectInfo(object_id="myselect", key=1, name="my select", options=["a", "b"])
    ]
    flags = VoiceAssistantFeature.VOICE_ASSISTANT
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[SelectState(key=1, state="a")],
        device_info={"voice_assistant_feature_flags": flags},
    )
    await hass.async_block_till_done()
    mac_address = device.device_info.mac_address

    await reconnect_with_updated_entity_info(
        hass, device, entity_info, device_info={"voice_assistant_feature_flags": 0}
    )
    for key in VOICE_ASSISTANT_SELECT_KEYS:
        assert not entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        ), key

    await reconnect_with_updated_entity_info(
        hass, device, entity_info, device_info={"voice_assistant_feature_flags": flags}
    )
    for key in VOICE_ASSISTANT_SELECT_KEYS:
        assert entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        ), key

    # A registry row is not an entity: the re-added select has to be live
    assert hass.states.get("select.test_wake_word") is not None


async def test_selects_removed_when_a_voice_assistant_goes_away(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test the voice assistant selects go when a device stops offering one."""
    entity_info = [
        SelectInfo(object_id="myselect", key=1, name="my select", options=["a", "b"])
    ]
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        states=[SelectState(key=1, state="a")],
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
        },
    )
    await hass.async_block_till_done()

    mac_address = device.device_info.mac_address
    for key in VOICE_ASSISTANT_SELECT_KEYS:
        assert entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        ), key

    await reconnect_with_updated_entity_info(
        hass, device, entity_info, device_info={"voice_assistant_feature_flags": 0}
    )

    for key in VOICE_ASSISTANT_SELECT_KEYS:
        assert not entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, f"{mac_address}-{key}"
        ), key

    # The device's own select is untouched: nothing is unloaded or reloaded
    state = hass.states.get("select.test_my_select")
    assert state is not None
    assert state.state == "a"


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_pipeline_selector(
    hass: HomeAssistant,
) -> None:
    """Test assist pipeline selector."""

    state = hass.states.get("select.test_assistant")
    assert state is not None
    assert state.state == "preferred"


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_secondary_pipeline_selector(
    hass: HomeAssistant,
) -> None:
    """Test secondary assist pipeline selector."""

    state = hass.states.get("select.test_assistant_2")
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


@pytest.mark.usefixtures("mock_voice_assistant_v1_entry")
async def test_secondary_wake_word_select(
    hass: HomeAssistant,
) -> None:
    """Test that secondary wake word select is unavailable initially."""
    state = hass.states.get("select.test_wake_word_2")
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
    state = hass.states.get("select.test_my_select")
    assert state is not None
    assert state.state == "a"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_my_select", ATTR_OPTION: "b"},
        blocking=True,
    )
    mock_client.select_command.assert_has_calls([call(1, "b", device_id=0)])


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
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert not satellite.async_get_configuration().available_wake_words

    # Selects should be unavailable
    for entity_id in ("select.test_wake_word", "select.test_wake_word_2"):
        state = hass.states.get(entity_id)
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
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert satellite.async_get_configuration().max_active_wake_words == 0

    # Selects should be unavailable
    for entity_id in ("select.test_wake_word", "select.test_wake_word_2"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNAVAILABLE


async def test_wake_word_select_no_active_wake_words(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test wake word select has no wake word selected if none are active."""
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
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None
    assert not satellite.async_get_configuration().active_wake_words

    # No wake words should be selected
    for entity_id in ("select.test_wake_word", "select.test_wake_word_2"):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == NO_WAKE_WORD


async def test_wake_word_select_first_active_wake_word(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test wake word select uses first available wake word if one is active."""
    device_config = AssistSatelliteConfiguration(
        available_wake_words=[
            AssistSatelliteWakeWord("okay_nabu", "Okay Nabu", ["en"]),
            AssistSatelliteWakeWord("hey_jarvis", "Hey Jarvis", ["en"]),
        ],
        active_wake_words=["okay_nabu"],
        max_active_wake_words=1,
    )
    mock_client.get_voice_assistant_configuration.return_value = device_config

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        device_info={
            "voice_assistant_feature_flags": VoiceAssistantFeature.VOICE_ASSISTANT
            | VoiceAssistantFeature.ANNOUNCE
        },
    )
    await hass.async_block_till_done()

    satellite = get_satellite_entity(hass, mock_device.device_info.mac_address)
    assert satellite is not None

    # First wake word should be selected
    state = hass.states.get("select.test_wake_word")
    assert state is not None
    assert state.state == "Okay Nabu"

    # Second wake word should not be selected
    state_2 = hass.states.get("select.test_wake_word_2")
    assert state_2 is not None
    assert state_2.state == NO_WAKE_WORD
