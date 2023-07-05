"""Test for the SmartThings media_player platform.

The only mocking required is of the underlying SmartThings API object so
real HTTP calls are not initiated during testing.
"""
from pysmartthings import Capability

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.smartthings.const import DOMAIN, SIGNAL_SMARTTHINGS_UPDATE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
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
            Capability.audio_mute,
            Capability.audio_volume,
            Capability.media_input_source,
            Capability.media_playback,
            Capability.media_playback_repeat,
            Capability.media_playback_shuffle,
            Capability.switch,
        ],
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


async def test_update_from_signal(hass: HomeAssistant, device_factory) -> None:
    """Test the media_player updates when receiving a signal."""
    # Arrange
    device = device_factory(
        "Media Player 1",
        [
            Capability.audio_mute,
            Capability.audio_volume,
            Capability.media_input_source,
            Capability.media_playback,
            Capability.media_playback_repeat,
            Capability.media_playback_shuffle,
            Capability.switch,
        ],
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
            Capability.audio_mute,
            Capability.audio_volume,
            Capability.media_input_source,
            Capability.media_playback,
            Capability.media_playback_repeat,
            Capability.media_playback_shuffle,
            Capability.switch,
        ],
    )
    config_entry = await setup_platform(hass, MEDIA_PLAYER_DOMAIN, devices=[device])
    config_entry.state = ConfigEntryState.LOADED
    # Act
    await hass.config_entries.async_forward_entry_unload(config_entry, "media_player")
    # Assert
    assert hass.states.get("media_player.media_player_1").state == STATE_UNAVAILABLE
