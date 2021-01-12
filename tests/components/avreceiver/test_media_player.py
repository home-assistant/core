"""Tests for the AVReceiver Media Player platform."""
from homeassistant.components.avreceiver.const import DOMAIN
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
)
from homeassistant.setup import async_setup_component


async def setup_platform(hass, config_entry, config):
    """Set up the media player platform for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_power(hass, config_entry, config, controller):
    """Test the volume mute service."""
    await setup_platform(hass, config_entry, config)
    zone = controller.main
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "media_player.test_device_main"},
        blocking=True,
    )
    zone.set_power.assert_called_with(True)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "media_player.test_device_main"},
        blocking=True,
    )
    zone.set_power.assert_called_with(False)
    zone.set_mute.reset_mock()


async def test_volume_mute(hass, config_entry, config, controller):
    """Test the volume mute service."""
    await setup_platform(hass, config_entry, config)
    zone = controller.main
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {
            ATTR_ENTITY_ID: "media_player.test_device_main",
            ATTR_MEDIA_VOLUME_MUTED: True,
        },
        blocking=True,
    )
    assert zone.set_mute.call_count == 1
    zone.set_mute.reset_mock()


async def test_volume_set(hass, config_entry, config, controller):
    """Test the volume set service."""
    await setup_platform(hass, config_entry, config)
    zone = controller.main
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_device_main", ATTR_MEDIA_VOLUME_LEVEL: 0},
        blocking=True,
    )
    zone.set_volume.assert_called_with(-80.0)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_device_main", ATTR_MEDIA_VOLUME_LEVEL: 1},
        blocking=True,
    )
    zone.set_volume.assert_called_with(0)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: "media_player.test_device_main", ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    zone.set_volume.assert_called_with(-40.0)
    zone.set_mute.reset_mock()
    zone.volume = -40
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {ATTR_ENTITY_ID: "media_player.test_device_main"},
        blocking=True,
    )
    zone.set_volume.assert_called_with(-37.0)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {ATTR_ENTITY_ID: "media_player.test_device_main"},
        blocking=True,
    )
    zone.set_volume.assert_called_with(-43.0)
    zone.set_mute.reset_mock()


async def test_select_input_source(hass, config_entry, config, controller):
    """Tests selecting input source and state."""
    await setup_platform(hass, config_entry, config)
    zone = controller.main
    # Test proper service called
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.test_device_main",
            ATTR_INPUT_SOURCE: "source1",
        },
        blocking=True,
    )
    zone.set_source.assert_called_with("source1")


async def test_select_sound_mode(hass, config_entry, config, controller):
    """Tests selecting input source and state."""
    await setup_platform(hass, config_entry, config)
    zone = controller.main
    # Test proper service called
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOUND_MODE,
        {
            ATTR_ENTITY_ID: "media_player.test_device_main",
            ATTR_SOUND_MODE: "AUTO",
        },
        blocking=True,
    )
    zone.set_soundmode.assert_called_with("AUTO")


async def test_unload_config_entry(hass, config_entry, config, controller):
    """Test the device is removed when the config entry is unloaded."""
    await setup_platform(hass, config_entry, config)
    await config_entry.async_unload(hass)
    assert not hass.states.get("media_player.test_device_main")
