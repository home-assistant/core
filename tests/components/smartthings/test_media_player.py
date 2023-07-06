"""Test for the SmartThings media_player platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Attribute, Capability

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_and_device_attributes(
    hass: HomeAssistant, device_factory
) -> None:
    """Test the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_input_source,
            Capability.switch,
        ],
        {
            Attribute.switch: "on",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
        },
    )
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Act
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("media_player.media_player_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device({(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == device.device_type_name
    assert entry.manufacturer == "Unavailable"


async def test_turn_off(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player turns of successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.switch,
            Capability.media_input_source,
        ],
        {
            Attribute.switch: "on",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == "off"


async def test_turn_on(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player turns on successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.switch,
            Capability.media_input_source,
        ],
        {
            Attribute.switch: "on",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == "on"


async def test_mute_volume(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player mutes volume successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.audio_mute,
            Capability.switch,
        ],
        {
            Attribute.mute: False,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: "media_player.media_player_1", "is_volume_muted": True},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["is_volume_muted"]


async def test_set_volume(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player sets volume successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 25,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.media_player_1", "volume_level": 0.5},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["volume_level"] == 0.5


async def test_volume_up(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player increases volume successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 25,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["volume_level"] == 0.26


async def test_volume_down(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player decreases volume successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 25,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["volume_level"] == 0.24


async def test_media_play(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player plays the media successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: "stopped",
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == MediaPlayerState.PLAYING


async def test_media_pause(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player pauses the media successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: "playing",
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == MediaPlayerState.PAUSED


async def test_media_stop(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player stops the media successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: "playing",
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {ATTR_ENTITY_ID: "media_player.media_player_1"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == MediaPlayerState.IDLE


async def test_select_source(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player selects the source successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_input_source,
            Capability.switch,
        ],
        {
            Attribute.input_source: "bluetooth",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.media_player_1", ATTR_INPUT_SOURCE: "wifi"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["source"] == "wifi"


async def test_shuffle_set(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player sets shuffle successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_playback_shuffle,
            Capability.switch,
        ],
        {
            Attribute.playback_shuffle: "off",
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SHUFFLE_SET,
        {ATTR_ENTITY_ID: "media_player.media_player_1", ATTR_MEDIA_SHUFFLE: True},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["shuffle"]


async def test_repeat_set(hass: HomeAssistant, device_factory) -> None:
    """Test if the media player sets repeat successfully."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_playback_repeat,
            Capability.switch,
        ],
        {
            Attribute.playback_repeat_mode: "off",
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_REPEAT_SET,
        {
            ATTR_ENTITY_ID: "media_player.media_player_1",
            ATTR_MEDIA_REPEAT: RepeatMode.ALL,
        },
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["repeat"] == RepeatMode.ALL


async def test_update_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the media_player updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_input_source,
            Capability.switch,
        ],
        {
            Attribute.switch: "off",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == "on"


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the media_player is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.media_input_source,
            Capability.switch,
        ],
        {
            Attribute.switch: "on",
            Attribute.supported_input_sources: ["bluetooth", "wifi"],
        },
    )
    config_entry = await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    config_entry.state = ConfigEntryState.LOADED
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "media_player")
    # Assert
    assert hass.states.get("media_player.media_player_1").state == STATE_UNAVAILABLE
