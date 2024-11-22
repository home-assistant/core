"""Test for the SmartThings media_player platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""

from pysmartthings import Attribute, Capability

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    MediaPlayerState,
)
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .conftest import setup_platform


async def test_entity_and_device_attributes(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device_factory,
) -> None:
    """Test if the attributes of the entity are correct."""
    # Arrange
    device = device_factory(
        "Media player 1",
        [Capability.media_playback],
        {
            Attribute.mnmo: "123",
            Attribute.mnmn: "Generic manufacturer",
            Attribute.mnhw: "v4.56",
            Attribute.mnfv: "v7.89",
        },
    )
    # Act
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Assert
    entry = entity_registry.async_get("media_player.media_player_1")
    assert entry
    assert entry.unique_id == device.device_id

    entry = device_registry.async_get_device(identifiers={(DOMAIN, device.device_id)})
    assert entry
    assert entry.configuration_url == "https://account.smartthings.com"
    assert entry.identifiers == {(DOMAIN, device.device_id)}
    assert entry.name == device.label
    assert entry.model == "123"
    assert entry.manufacturer == "Generic manufacturer"
    assert entry.hw_version == "v4.56"
    assert entry.sw_version == "v7.89"


async def test_turn_on(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player turns on successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: MediaPlayerState.OFF,
            Attribute.switch: "off",
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
    assert state.state == MediaPlayerState.ON


async def test_turn_off(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player turns off successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: MediaPlayerState.ON,
            Attribute.switch: "on",
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
    assert state.state == MediaPlayerState.OFF


async def test_mute_volume(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player mutes volume successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
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
        {
            ATTR_ENTITY_ID: "media_player.media_player_1",
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True


async def test_unmute(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player unmutes volume successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.audio_mute,
            Capability.switch,
        ],
        {
            Attribute.mute: True,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.media_player_1",
            ATTR_MEDIA_VOLUME_MUTED: False,
        },
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False


async def test_volume_set(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player sets volume successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 50,
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.media_player_1",
            ATTR_MEDIA_VOLUME_LEVEL: 0.6,
        },
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.6


async def test_volume_up(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player increases volume successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 50,
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
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.51


async def test_volume_down(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player decreases volume successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.audio_volume,
            Capability.switch,
        ],
        {
            Attribute.volume: 50,
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
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.49


async def test_media_play(hass: HomeAssistant, device_factory) -> None:
    """Test if the media_player plays a media successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: MediaPlayerState.IDLE,
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
    """Test if the media_player pauses a media successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: MediaPlayerState.PLAYING,
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
    """Test if the media_player stops a media successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_playback,
            Capability.switch,
        ],
        {
            Attribute.playback_status: MediaPlayerState.PLAYING,
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
    """Test if the media_player selects a source successfully."""
    # Arrange
    device = device_factory(
        "Media_player_1",
        [
            Capability.media_input_source,
            Capability.switch,
        ],
        {
            Attribute.input_source: "HDMI1",
            Attribute.supported_input_sources: ["HDM1", "HDMI2", "wifi"],
            Attribute.switch: "on",
        },
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    # Act
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: "media_player.media_player_1", ATTR_INPUT_SOURCE: "HDMI2"},
        blocking=True,
    )
    # Assert
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.attributes["source"] == "HDMI2"


async def test_update_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the media_player updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Media player 1",
        [Capability.media_playback],
        {Attribute.playback_status: MediaPlayerState.OFF},
    )
    await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    await device.switch_on(True)
    # Act
    async_dispatcher_send(hass, SIGNAL_SMARTTHINGS_UPDATE, [device.device_id])
    # Assert
    await hass.async_block_till_done()
    state = hass.states.get("media_player.media_player_1")
    assert state is not None
    assert state.state == MediaPlayerState.ON


async def test_unload_config_entry(hass: HomeAssistant, device_factory) -> None:
    """Test the media_player is removed when the config entry is unloaded."""
    # Arrange
    device = device_factory(
        "Media player 1",
        [Capability.media_playback],
        {Attribute.playback_status: MediaPlayerState.OFF},
    )
    config_entry = await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    config_entry.mock_state(hass, ConfigEntryState.LOADED)
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "media_player")
    # Assert
    assert hass.states.get("media_player.media_player_1").state == STATE_UNAVAILABLE
