import asyncio
import logging
import re
from enum import Enum

import aiohttp

from .const import BUTTON_TYPE_PARAM_VALUE, SWITCH_TYPE_ENABLE, PARAM_MOTION_DETECT, PARAM_STATUS, PARAM_STORAGE_USED, \
    PARAM_NIGHT_VISION_MODE, PARAM_MODE, PARAM_CURRENT_OPTION, PARAM_MODES, PARAM_OPTIONS, PARAM_CHANNELS, \
    PARAM_CHANNEL_ID, PARAM_USED_BYTES, PARAM_TOTAL_BYTES, PARAM_STREAMS, PARAM_HLS, PARAM_RESTART_DEVICE, PARAM_URL, \
    PARAM_CLOSE_CAMERA, PARAM_WHITE_LIGHT, PARAM_AB_ALARM_SOUND, PARAM_AUDIO_ENCODE_CONTROL, CONF_CLOSE_CAMERA, \
    CONF_WHITE_LIGHT, CONF_AB_ALARM_SOUND, CONF_AUDIO_ENCODE_CONTROL, CONF_NVM, PARAM_STREAM_ID, CONF_PT
from pyimouapi import RequestFailedException
from pyimouapi.device import ImouDeviceManager

_LOGGER: logging.Logger = logging.getLogger(__package__)

PATTERN = re.compile(r'^\d+$')


class ImouHaDevice(object):
    def __init__(self, device_id: str, channel_id: str, channel_name: str,
                 manufacturer: str, model: str, swversion: str, product_id: str):
        self._device_id = device_id
        self._channel_id = str(channel_id) if isinstance(channel_id, int) else channel_id
        self._channel_name = channel_name
        self._manufacturer = manufacturer
        self._model = model
        self._swversion = swversion
        self._switches = {
            PARAM_MOTION_DETECT: False
        }
        self._sensors = {
            PARAM_STATUS: DeviceStatus.OFFLINE.status,
            PARAM_STORAGE_USED: "Abnormal"
        }

        self._selects = {

        }
        self._buttons = ["restart_device"]
        self._product_id = product_id

    @property
    def device_id(self):
        return self._device_id

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def channel_name(self):
        return self._channel_name

    @property
    def manufacturer(self):
        return self._manufacturer

    @property
    def model(self):
        return self._model

    @property
    def swversion(self):
        return self._swversion

    @property
    def switches(self):
        return self._switches

    @property
    def sensors(self):
        return self._sensors

    @property
    def selects(self):
        return self._selects

    @property
    def buttons(self):
        return self._buttons

    @property
    def product_id(self) -> str:
        return self._product_id

    def set_product_id(self, product_id: str) -> None:
        self._product_id = product_id

    def __str__(self):
        return f"{self.device_id} {self.channel_id} {self.channel_name} {self.manufacturer} {self.model} {self.product_id} {self.swversion} {self.switches} {self.sensors} {self._selects}"


def get_device_status(origin_value: str):
    try:
        for status in DeviceStatus:
            if status.origin_value == origin_value:
                return status.status
        return DeviceStatus.OFFLINE.status
    except Exception as e:
        _LOGGER.info(f"An error occurred: {e}")
        return DeviceStatus.OFFLINE.status


class ImouHaDeviceManager(object):
    def __init__(self, device_manager: ImouDeviceManager):
        self._device_manager = device_manager

    @property
    def device_manager(self):
        return self._device_manager

    async def async_update_device_status(self, device: ImouHaDevice):
        """Update device status, with the updater calling every time the coordinator is updated"""
        await asyncio.gather(
            self.async_update_device_switch_status(device),
            self.async_update_device_select_status(device),
            self.async_update_device_sensor_status(device),
            return_exceptions=True
        )
        _LOGGER.info(f"update_device_status finish: {device.__str__()}")

    async def async_update_device_switch_status(self, device):
        """UPDATE SWITCH STATUS"""
        for switch_type in device.switches.keys():
            device.switches[switch_type] = any(await asyncio.gather(
                *[self._async_update_device_switch_status_by_ability(device, ability_type) for ability_type in
                  SWITCH_TYPE_ENABLE[switch_type]], return_exceptions=True))

    async def async_update_device_select_status(self, device):
        """UPDATE SELECT STATUS"""
        for select_type in device.selects.keys():
            await self.async_update_device_select_status_by_type(device, select_type)

    async def async_update_device_sensor_status(self, device):
        """UPDATE SENSOR STATUS"""
        for sensor_type in device.sensors.keys():
            if sensor_type == PARAM_STATUS:
                try:
                    data = await self.device_manager.async_get_device_online_status(device.device_id)
                    for channel in data[PARAM_CHANNELS]:
                        if channel[PARAM_CHANNEL_ID] == device.channel_id:
                            device.sensors[PARAM_STATUS] = get_device_status(channel["onLine"])
                            break
                except RequestFailedException:
                    device.sensors[PARAM_STATUS] = DeviceStatus.OFFLINE.status
            elif sensor_type == PARAM_STORAGE_USED:
                await self._get_device_storage(device)

    async def _get_device_storage(self, device):
        try:
            data = await self.device_manager.async_get_device_storage(device.device_id)
            if data[PARAM_TOTAL_BYTES] != 0:
                percentage_used = int(data[PARAM_USED_BYTES] * 100 / data[PARAM_TOTAL_BYTES])
                device.sensors[PARAM_STORAGE_USED] = f"{percentage_used}%"
            else:
                device.sensors[PARAM_STORAGE_USED] = "No Storage Medium"
        except RequestFailedException as exception:
            if "DV1049" in exception.message:
                device.sensors[PARAM_STORAGE_USED] = "No Storage Medium"
            else:
                device.sensors[PARAM_STORAGE_USED] = "Abnormal"

    async def async_get_device_stream(self, device):
        try:
            return await self.async_get_device_exist_stream(device)
        except RequestFailedException as exception:
            if "LV1002" in exception.message:
                try:
                    return await self.async_create_device_stream(device)
                except RequestFailedException as ex:
                    if "LV1001" in ex.message:
                        return await self.async_get_device_exist_stream(device)
        raise RequestFailedException("get_stream_url failed")

    async def async_get_device_exist_stream(self, device):
        data = await self.device_manager.async_get_stream_url(device.device_id, device.channel_id)
        if PARAM_STREAMS in data and len(data[PARAM_STREAMS]) > 0:
            # Prioritize obtaining high-definition live streaming addresses for HTTPS
            for stream in data[PARAM_STREAMS]:
                if "https" in stream[PARAM_HLS] and stream[PARAM_STREAM_ID] == 0:
                    _LOGGER.info(f"create_device_stream {stream[PARAM_HLS]}")
                    return stream[PARAM_HLS]
            return data[PARAM_STREAMS][0][PARAM_HLS]

    async def async_create_device_stream(self, device):
        data = await self.device_manager.async_create_stream_url(device.device_id, device.channel_id)
        if PARAM_STREAMS in data and len(data[PARAM_STREAMS]) > 0:
            # Prioritize obtaining high-definition live streaming addresses for HTTPS
            for stream in data[PARAM_STREAMS]:
                if "https" in stream[PARAM_HLS] and stream[PARAM_STREAM_ID] == 0:
                    _LOGGER.info(f"create_device_stream {stream[PARAM_HLS]}")
                    return stream[PARAM_HLS]
            return data[PARAM_STREAMS][0][PARAM_HLS]

    async def async_get_device_image(self, device):
        data = await self.device_manager.async_get_device_snap(device.device_id, device.channel_id)
        if PARAM_URL in data:
            await asyncio.sleep(3)
        try:
            async with aiohttp.ClientSession() as session:
                response = await session.request("GET", data[PARAM_URL])
                if response.status != 200:
                    raise RequestFailedException(f"request failed,status code {response.status}")
                return await response.read()
        except Exception as exception:
            _LOGGER.info("error get_device_image %s", exception)
            return None

    async def async_get_devices(self) -> list[ImouHaDevice]:
        """
        GET A LIST OF ALL DEVICES。
        """
        devices = []
        for device in await self.device_manager.async_get_devices():
            if device.channel_number > 0 and len(device.channels) > 0:
                for channel in device.channels:
                    imou_ha_device = ImouHaDevice(device.device_id, channel.channel_id,
                                                  channel.channel_name, device.brand, device.device_model,
                                                  device.device_version, device.product_id)
                    # Determine which switches are needed based on the ability
                    abilities = device.device_ability if len(device.channels) == 1 else channel.channel_ability
                    if CONF_CLOSE_CAMERA in abilities:
                        imou_ha_device.switches[PARAM_CLOSE_CAMERA] = False
                    if CONF_WHITE_LIGHT in abilities:
                        imou_ha_device.switches[PARAM_WHITE_LIGHT] = False
                    if CONF_AB_ALARM_SOUND in abilities:
                        imou_ha_device.switches[PARAM_AB_ALARM_SOUND] = False
                    if CONF_AUDIO_ENCODE_CONTROL in abilities:
                        imou_ha_device.switches[PARAM_AUDIO_ENCODE_CONTROL] = False
                    if CONF_NVM in abilities:
                        imou_ha_device.selects[PARAM_NIGHT_VISION_MODE] = {
                            PARAM_CURRENT_OPTION: "",
                            PARAM_OPTIONS: []
                        }
                    if CONF_PT in abilities:
                        imou_ha_device.buttons.extend(["ptz_up", "ptz_down", "ptz_left", "ptz_right"])

                    devices.append(imou_ha_device)
        return devices

    async def async_press_button(self, device_id: str, channel_id: str, button_type: str):
        if "ptz" in button_type:
            await self.device_manager.async_control_device_ptz(device_id, channel_id,
                                                               BUTTON_TYPE_PARAM_VALUE[button_type])
        elif PARAM_RESTART_DEVICE == button_type:
            await self.device_manager.async_restart_device(device_id)

    async def async_switch_operation(self, device, switch_type: str, enable: bool):
        if PARAM_MOTION_DETECT == switch_type:
            await self.device_manager.async_modify_device_alarm_status(device.device_id, device.channel_id, enable)
        else:
            result = await asyncio.gather(
                *[self._async_set_device_switch_status_by_ability(device, ability_type, enable)
                  for ability_type in SWITCH_TYPE_ENABLE[switch_type]],
                return_exceptions=True)
            # Request all failed, consider this operation a failure
            if all(isinstance(result_item, Exception) for result_item in result):
                raise result[0]
        await asyncio.sleep(3)
        device.switches[switch_type] = any(await asyncio.gather(
            *[self._async_update_device_switch_status_by_ability(device, ability_type) for ability_type in
              SWITCH_TYPE_ENABLE[switch_type]], return_exceptions=True))

    async def async_select_option(self, device, select_type: str, option: str):
        if PARAM_NIGHT_VISION_MODE == select_type:
            await self.device_manager.async_set_device_night_vision_mode(device.device_id, device.channel_id, option)

    async def _async_update_device_switch_status_by_ability(self, device, ability_type) -> bool:
        # Updating the interface requires capturing exceptions for two main purposes:
        # 1. To prevent the updater from failing to load due to exceptions;
        # 2. To set default values
        try:
            data = await self.device_manager.async_get_device_status(device.device_id, device.channel_id,
                                                                     ability_type)
            return data[PARAM_STATUS] == "on"
        except RequestFailedException:
            return False

    async def _async_set_device_switch_status_by_ability(self, device, ability_type, enable: bool) -> None:
        await self.device_manager.async_set_device_status(device.device_id, device.channel_id, ability_type, enable)

    async def async_update_device_select_status_by_type(self, device, select_type):
        if select_type == PARAM_NIGHT_VISION_MODE:
            try:
                await self._async_update_device_night_vision_mode(device)
            except RequestFailedException:
                device.selects[PARAM_NIGHT_VISION_MODE] = {
                    PARAM_CURRENT_OPTION: "",
                    PARAM_OPTIONS: []
                }

    async def _async_update_device_night_vision_mode(self, device):
        data = await self.device_manager.async_get_device_night_vision_mode(device.device_id,
                                                                            device.channel_id)
        if PARAM_MODE not in data or PARAM_MODES not in data:
            raise RequestFailedException("get_device_night_vision fail")
        if data[PARAM_MODE] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_CURRENT_OPTION] = data[PARAM_MODE]
        if data[PARAM_MODES] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_OPTIONS] = data[PARAM_MODES]


class DeviceStatus(Enum):
    ONLINE = ("1", "online")
    OFFLINE = ("0", "offline")
    SLEEP = ("4", "sleep")
    UPGRADING = ("3", "upgrading")

    def __init__(self, origin_value, status):
        self.origin_value = origin_value
        self.status = status
