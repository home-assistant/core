"""Test the songpal integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from songpal import SongpalException
from songpal.containers import Sysinfo

from homeassistant.components.songpal.const import CONF_ENDPOINT
from homeassistant.const import CONF_NAME

FRIENDLY_NAME = "name"
ENTITY_ID = f"media_player.{FRIENDLY_NAME}"
HOST = "0.0.0.0"
ENDPOINT = f"http://{HOST}:10000/sony"
MODEL = "model"
MAC = "mac"
WIRELESS_MAC = "wmac"
SW_VERSION = "sw_ver"

CONF_DATA = {
    CONF_NAME: FRIENDLY_NAME,
    CONF_ENDPOINT: ENDPOINT,
}


def _create_mocked_device(
    throw_exception=False,
    wired_mac=MAC,
    wireless_mac=None,
    no_soundfield=False,
    with_zones=False,
):
    mocked_device = MagicMock()

    zones = []
    if with_zones:
        zone1 = MagicMock()
        zone1.title = "Main Zone"
        zone1.uri = "extOutput:zone?zone=1"
        zone1.active = True
        zone1.activate = AsyncMock()
        mocked_device.zone1 = zone1

        zone2 = MagicMock()
        zone2.title = "Zone 2"
        zone2.uri = "extOutput:zone?zone=2"
        zone2.active = True
        zone2.activate = AsyncMock()
        mocked_device.zone2 = zone2

        zone3 = MagicMock()
        zone3.title = "Zone 3"
        zone3.uri = "extOutput:zone?zone=3"
        zone3.active = False
        zone3.activate = AsyncMock()
        mocked_device.zone3 = zone3

        zones = [zone1, zone2, zone3]

    type(mocked_device).get_supported_methods = AsyncMock(
        side_effect=SongpalException("Unable to do POST request: ")
        if throw_exception
        else None
    )

    interface_info = MagicMock()
    interface_info.modelName = MODEL
    type(mocked_device).get_interface_information = AsyncMock(
        return_value=interface_info
    )

    sys_info = Sysinfo(
        bdAddr=None,
        macAddr=wired_mac,
        wirelessMacAddr=wireless_mac,
        bssid=None,
        ssid=None,
        bleID=None,
        serialNumber=None,
        generation=None,
        model=None,
        version=SW_VERSION,
    )
    type(mocked_device).get_system_info = AsyncMock(return_value=sys_info)

    volume1 = MagicMock()
    volume1.maxVolume = 100
    volume1.minVolume = 0
    volume1.volume = 50
    volume1.is_muted = False
    volume1.output = "extOutput:zone?zone=1" if with_zones else ""
    volume1.set_volume = AsyncMock()
    volume1.set_mute = AsyncMock()
    volume2 = MagicMock()
    volume2.maxVolume = 100
    volume2.minVolume = 0
    volume2.volume = 20
    volume2.is_muted = True
    volume2.output = "extOutput:zone?zone=2" if with_zones else ""
    mocked_device.volume1 = volume1
    mocked_device.volume2 = volume2
    type(mocked_device).get_volume_information = AsyncMock(
        return_value=[volume1, volume2]
    )

    power = MagicMock()
    power.status = True
    type(mocked_device).get_power = AsyncMock(return_value=power)

    input1 = MagicMock()
    input1.title = "title1"
    input1.uri = "uri1"
    input1.active = False
    input1.outputs = [zone.uri for zone in zones] if with_zones else []
    input1.activate = AsyncMock()
    mocked_device.input1 = input1
    input2 = MagicMock()
    input2.title = "title2"
    input2.uri = "uri2"
    input2.active = True
    input2.outputs = [zones[0].uri] if with_zones else []
    input2.activate = AsyncMock()
    mocked_device.input2 = input2
    type(mocked_device).get_inputs = AsyncMock(return_value=[input1, input2])

    if with_zones:
        type(mocked_device).get_zones = AsyncMock(return_value=zones)
    else:
        type(mocked_device).get_zones = AsyncMock(
            side_effect=SongpalException("Device has no zones")
        )

    async def _get_zone(name: str):
        for zone in zones:
            if zone.title == name:
                return zone
        raise SongpalException(f"Unable to find zone {name}")

    type(mocked_device).get_zone = AsyncMock(side_effect=_get_zone)

    sound_mode1 = MagicMock()
    sound_mode1.title = "Sound Mode 1"
    sound_mode1.value = "sound_mode1"
    sound_mode1.isAvailable = True
    sound_mode2 = MagicMock()
    sound_mode2.title = "Sound Mode 2"
    sound_mode2.value = "sound_mode2"
    sound_mode2.isAvailable = True
    sound_mode3 = MagicMock()
    sound_mode3.title = "Sound Mode 3"
    sound_mode3.value = "sound_mode3"
    sound_mode3.isAvailable = False

    soundField = MagicMock()
    soundField.currentValue = "sound_mode2"
    soundField.candidate = [sound_mode1, sound_mode2, sound_mode3]

    settings = MagicMock()
    settings.target = "soundField"
    settings.__iter__.return_value = [soundField]

    type(mocked_device).get_sound_settings = AsyncMock(
        return_value=[] if no_soundfield else [settings]
    )

    type(mocked_device).set_power = AsyncMock()
    type(mocked_device).set_sound_settings = AsyncMock()
    type(mocked_device).listen_notifications = AsyncMock()
    type(mocked_device).stop_listen_notifications = AsyncMock()

    notification_callbacks = {}
    mocked_device.notification_callbacks = notification_callbacks

    def _on_notification(name, callback):
        notification_callbacks[name] = callback

    type(mocked_device).on_notification = MagicMock(side_effect=_on_notification)
    type(mocked_device).clear_notification_callbacks = MagicMock()

    return mocked_device


def _patch_config_flow_device(mocked_device):
    return patch(
        "homeassistant.components.songpal.config_flow.Device",
        return_value=mocked_device,
    )


def _patch_media_player_device(mocked_device):
    return patch(
        "homeassistant.components.songpal.media_player.Device",
        return_value=mocked_device,
    )
