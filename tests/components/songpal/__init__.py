"""Test the songpal integration."""
from songpal import SongpalException

from homeassistant.components.songpal.const import CONF_ENDPOINT
from homeassistant.const import CONF_NAME

from tests.async_mock import AsyncMock, MagicMock, patch

FRIENDLY_NAME = "friendly name"
HOST = "0.0.0.0"
ENDPOINT = f"http://{HOST}:10000/sony"
MODEL = "model"
MAC = "mac"
SW_VERSION = "sw_ver"

CONF_DATA = {
    CONF_NAME: FRIENDLY_NAME,
    CONF_ENDPOINT: ENDPOINT,
}


def _create_mocked_device(throw_exception=False):
    mocked_device = MagicMock()

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

    sys_info = MagicMock()
    sys_info.macAddr = MAC
    sys_info.version = SW_VERSION
    type(mocked_device).get_system_info = AsyncMock(return_value=sys_info)

    volume1 = MagicMock()
    volume1.maxVolume = 100
    volume1.minVolume = 0
    volume1.volume = 50
    volume1.is_muted = False
    volume1.set_volume = AsyncMock()
    volume1.set_mute = AsyncMock()
    mocked_device.volume1 = volume1
    type(mocked_device).get_volume_information = AsyncMock(return_value=[volume1])

    power = MagicMock()
    power.status = True
    type(mocked_device).get_power = AsyncMock(return_value=power)

    input1 = MagicMock()
    input1.title = "title1"
    input1.uri = "uri1"
    input1.active = False
    input1.activate = AsyncMock()
    mocked_device.input1 = input1
    input2 = MagicMock()
    input2.title = "title2"
    input2.uri = "uri2"
    input2.active = True
    type(mocked_device).get_inputs = AsyncMock(return_value=[input1, input2])

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
