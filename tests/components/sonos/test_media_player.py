"""Tests for the Sonos Media Player platform."""
from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    CONNECTION_UPNP,
    DeviceRegistry,
)

from .conftest import MockSoCo, SoCoMockFactory, tests_setup_hass


async def test_device_registry(
    hass: HomeAssistant, device_registry: DeviceRegistry, async_autosetup_sonos, soco
) -> None:
    """Test sonos device registered in the device registry."""
    reg_device = device_registry.async_get_device(
        identifiers={("sonos", "RINCON_test")}
    )
    assert reg_device is not None
    assert reg_device.model == "Model Name"
    assert reg_device.sw_version == "13.1"
    assert reg_device.connections == {
        (CONNECTION_NETWORK_MAC, "00:11:22:33:44:55"),
        (CONNECTION_UPNP, "uuid:RINCON_test"),
    }
    assert reg_device.manufacturer == "Sonos"
    assert reg_device.name == "Zone A"
    # Default device provides battery info, area should not be suggested
    assert reg_device.suggested_area is None


async def test_device_registry_not_portable(
    hass: HomeAssistant, device_registry: DeviceRegistry, async_setup_sonos, soco
) -> None:
    """Test non-portable sonos device registered in the device registry to ensure area suggested."""
    soco.get_battery_info.return_value = {}
    await async_setup_sonos()

    reg_device = device_registry.async_get_device(
        identifiers={("sonos", "RINCON_test")}
    )
    assert reg_device is not None
    assert reg_device.suggested_area == "Zone A"


async def test_entity_basic(
    hass: HomeAssistant, async_autosetup_sonos, discover
) -> None:
    """Test basic state and attributes."""
    state = hass.states.get("media_player.zone_a")
    assert state.state == STATE_IDLE
    attributes = state.attributes
    assert attributes["friendly_name"] == "Zone A"
    assert attributes["is_volume_muted"] is False
    assert attributes["volume_level"] == 0.19


async def test_play_media_music_library_album_artist(
    hass: HomeAssistant,
    soco_factory: SoCoMockFactory,
) -> None:
    """Test that multiple albums are added to queue for A:ALBUMARTIST."""
    soco_1 = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_1.music_library.get_music_library_information.return_value = [
        "Album_1",
        "Album_2",
    ]
    await tests_setup_hass(hass)
    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            "entity_id": "media_player.living_room",
            "media_content_type": "album",
            "media_content_id": "A:ALBUMARTIST/Beatles",
        },
        blocking=True,
    )
    # Verify queue is cleared
    assert soco_1.clear_queue.call_count == 1
    # Verify both albums are added to queue
    assert soco_1.add_to_queue.call_count == 2
    assert soco_1.add_to_queue.call_args_list[0].args[0] == "Album_1"
    assert soco_1.add_to_queue.call_args_list[1].args[0] == "Album_2"
    # Verify queue is played from start.
    assert soco_1.play_from_queue.call_count == 1
    assert soco_1.play_from_queue.call_args_list[0].args[0] == 0
