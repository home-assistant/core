"""The foscam coordinator object."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta

from libpyfoscamcgi import FoscamCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER

type FoscamConfigEntry = ConfigEntry[FoscamCoordinator]


@dataclass
class FoscamDeviceInfo:
    """A data class representing the current state and configuration of a Foscam camera device."""

    dev_info: dict
    product_info: dict

    is_open_ir: bool
    is_flip: bool
    is_mirror: bool

    is_asleep: dict
    is_open_white_light: bool
    is_siren_alarm: bool

    device_volume: int
    speak_volume: int
    is_turn_off_volume: bool
    is_turn_off_light: bool
    supports_speak_volume_adjustment: bool
    supports_pet_adjustment: bool
    supports_car_adjustment: bool
    supports_human_adjustment: bool
    supports_wdr_adjustment: bool
    supports_hdr_adjustment: bool

    is_open_wdr: bool | None = None
    is_open_hdr: bool | None = None
    is_pet_detection_on: bool | None = None
    is_car_detection_on: bool | None = None
    is_human_detection_on: bool | None = None


class FoscamCoordinator(DataUpdateCoordinator[FoscamDeviceInfo]):
    """Foscam coordinator."""

    config_entry: FoscamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FoscamConfigEntry,
        session: FoscamCamera,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.session = session

    def gather_all_configs(self) -> FoscamDeviceInfo:
        """Get all Foscam configurations."""
        ret_dev_info, dev_info = self.session.get_dev_info()
        dev_info = dev_info if ret_dev_info == 0 else {}

        ret_product_info, product_info = self.session.get_product_all_info()
        product_info = product_info if ret_product_info == 0 else {}

        ret_ir, infra_led_config = self.session.get_infra_led_config()
        is_open_ir = infra_led_config["mode"] == "1" if ret_ir == 0 else False

        ret_mf, mirror_flip_setting = self.session.get_mirror_and_flip_setting()
        is_flip = mirror_flip_setting["isFlip"] == "1" if ret_mf == 0 else False
        is_mirror = mirror_flip_setting["isMirror"] == "1" if ret_mf == 0 else False

        ret_sleep, sleep_setting = self.session.is_asleep()
        is_asleep = {"supported": ret_sleep == 0, "status": bool(int(sleep_setting))}

        ret_wl, is_open_white_light = self.session.getWhiteLightBrightness()
        is_open_white_light_val = (
            is_open_white_light["enable"] == "1" if ret_wl == 0 else False
        )

        ret_sc, is_siren_alarm = self.session.getSirenConfig()
        is_siren_alarm_val = (
            is_siren_alarm["sirenEnable"] == "1" if ret_sc == 0 else False
        )

        ret_vol, volume = self.session.getAudioVolume()
        volume_val = int(volume["volume"]) if ret_vol == 0 else 0

        ret_sv, speak_volume = self.session.getSpeakVolume()
        speak_volume_val = int(speak_volume["SpeakVolume"]) if ret_sv == 0 else 0

        ret_ves, is_turn_off_volume = self.session.getVoiceEnableState()
        is_turn_off_volume_val = not (
            ret_ves == 0 and is_turn_off_volume["isEnable"] == "1"
        )

        ret_les, is_turn_off_light = self.session.getLedEnableState()
        is_turn_off_light_val = not (
            ret_les == 0 and is_turn_off_light["isEnable"] == "0"
        )

        is_open_wdr = None
        is_open_hdr = None
        reserve3 = product_info.get("reserve4")
        model = product_info.get("model")
        model_int = int(model) if model is not None else 7002
        if model_int > 7001:
            reserve3_int = int(reserve3) if reserve3 is not None else 0
            supports_wdr_adjustment_val = bool(int(reserve3_int & 256))
            supports_hdr_adjustment_val = bool(int(reserve3_int & 128))
            if supports_wdr_adjustment_val:
                ret_wdr, is_open_wdr_data = self.session.getWdrMode()
                mode = (
                    is_open_wdr_data["mode"] if ret_wdr == 0 and is_open_wdr_data else 0
                )
                is_open_wdr = bool(int(mode))
            elif supports_hdr_adjustment_val:
                ret_hdr, is_open_hdr_data = self.session.getHdrMode()
                mode = (
                    is_open_hdr_data["mode"] if ret_hdr == 0 and is_open_hdr_data else 0
                )
                is_open_hdr = bool(int(mode))
        else:
            supports_wdr_adjustment_val = False
            supports_hdr_adjustment_val = False
        ret_sw, software_capabilities = self.session.getSWCapabilities()
        supports_speak_volume_adjustment_val = (
            bool(int(software_capabilities.get("swCapabilities1")) & 32)
            if ret_sw == 0
            else False
        )
        pet_adjustment_val = (
            bool(int(software_capabilities.get("swCapabilities2")) & 512)
            if ret_sw == 0
            else False
        )
        car_adjustment_val = (
            bool(int(software_capabilities.get("swCapabilities2")) & 256)
            if ret_sw == 0
            else False
        )
        human_adjustment_val = (
            bool(int(software_capabilities.get("swCapabilities2")) & 128)
            if ret_sw == 0
            else False
        )
        ret_md, motion_config_val = self.session.get_motion_detect_config()
        if pet_adjustment_val:
            is_pet_detection_on_val = (
                motion_config_val.get("petEnable") == "1" if ret_md == 0 else False
            )
        else:
            is_pet_detection_on_val = False

        if car_adjustment_val:
            is_car_detection_on_val = (
                motion_config_val.get("carEnable") == "1" if ret_md == 0 else False
            )
        else:
            is_car_detection_on_val = False

        if human_adjustment_val:
            is_human_detection_on_val = (
                motion_config_val.get("humanEnable") == "1" if ret_md == 0 else False
            )
        else:
            is_human_detection_on_val = False

        return FoscamDeviceInfo(
            dev_info=dev_info,
            product_info=product_info,
            is_open_ir=is_open_ir,
            is_flip=is_flip,
            is_mirror=is_mirror,
            is_asleep=is_asleep,
            is_open_white_light=is_open_white_light_val,
            is_siren_alarm=is_siren_alarm_val,
            device_volume=volume_val,
            speak_volume=speak_volume_val,
            is_turn_off_volume=is_turn_off_volume_val,
            is_turn_off_light=is_turn_off_light_val,
            supports_speak_volume_adjustment=supports_speak_volume_adjustment_val,
            supports_pet_adjustment=pet_adjustment_val,
            supports_car_adjustment=car_adjustment_val,
            supports_human_adjustment=human_adjustment_val,
            supports_hdr_adjustment=supports_hdr_adjustment_val,
            supports_wdr_adjustment=supports_wdr_adjustment_val,
            is_open_wdr=is_open_wdr,
            is_open_hdr=is_open_hdr,
            is_pet_detection_on=is_pet_detection_on_val,
            is_car_detection_on=is_car_detection_on_val,
            is_human_detection_on=is_human_detection_on_val,
        )

    async def _async_update_data(self) -> FoscamDeviceInfo:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(10):
            return await self.hass.async_add_executor_job(self.gather_all_configs)
