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

    is_openir: bool
    is_flip: bool
    is_mirror: bool

    is_asleep: dict
    is_openwhitelight: bool
    is_sirenalarm: bool

    volume: int
    speakvolume: int
    is_turnoffvolume: bool
    is_turnofflight: bool

    is_openwdr: bool | None = None
    is_openhdr: bool | None = None


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
        is_openir = infra_led_config["mode"] if ret_ir == 0 and infra_led_config else 0

        ret_mf, mirror_flip_setting = self.session.get_mirror_and_flip_setting()
        is_flip = (
            mirror_flip_setting["isFlip"] if ret_mf == 0 and mirror_flip_setting else 0
        )
        is_mirror = (
            mirror_flip_setting["isMirror"]
            if ret_mf == 0 and mirror_flip_setting
            else 0
        )

        ret_sleep, sleep_setting = self.session.is_asleep()
        is_asleep = {"supported": ret_sleep == 0, "status": sleep_setting}

        ret_wl, is_open_white_light = self.session.getWhiteLightBrightness()
        is_open_white_light_val = (
            is_open_white_light["enable"] if ret_wl == 0 and is_open_white_light else 0
        )

        ret_sc, is_siren_alarm = self.session.getSirenConfig()
        is_siren_alarm_val = (
            is_siren_alarm["sirenEnable"] if ret_sc == 0 and is_siren_alarm else 0
        )

        ret_vol, volume = self.session.getAudioVolume()
        volume_val = volume["volume"] if ret_vol == 0 and volume else 0

        ret_sv, speak_volume = self.session.getSpeakVolume()
        speak_volume_val = (
            speak_volume["SpeakVolume"] if ret_sv == 0 and speak_volume else 0
        )

        ret_ves, is_turn_off_volume = self.session.getVoiceEnableState()
        is_turn_off_volume_val = (
            0 if (ret_ves == 0 and int(is_turn_off_volume["isEnable"]) == 1) else 1
        )

        ret_les, is_turn_off_light = self.session.getLedEnableState()
        is_turn_off_light_val = (
            0 if (ret_les == 0 and int(is_turn_off_light["isEnable"]) == 1) else 1
        )

        is_open_wdr = None
        is_open_hdr = None
        reserve3 = product_info.get("reserve3")
        try:
            reserve3_int = int(reserve3) if reserve3 is not None else 0
        except (TypeError, ValueError):
            reserve3_int = 0

        if (reserve3_int & (1 << 8)) != 0:
            ret_wdr, is_open_wdr_data = self.session.getWdrMode()
            mode = is_open_wdr_data["mode"] if ret_wdr == 0 and is_open_wdr_data else 0
            is_open_wdr = bool(int(mode))
        else:
            ret_hdr, is_open_hdr_data = self.session.getHdrMode()
            mode = is_open_hdr_data["mode"] if ret_hdr == 0 and is_open_hdr_data else 0
            is_open_hdr = bool(int(mode))

        return FoscamDeviceInfo(
            dev_info=dev_info,
            product_info=product_info,
            is_openir=bool(int(is_openir)),
            is_flip=bool(int(is_flip)),
            is_mirror=bool(int(is_mirror)),
            is_asleep=is_asleep,
            is_openwhitelight=bool(int(is_open_white_light_val)),
            is_sirenalarm=bool(int(is_siren_alarm_val)),
            volume=volume_val,
            speakvolume=speak_volume_val,
            is_turnoffvolume=bool(int(is_turn_off_volume_val)),
            is_turnofflight=bool(int(is_turn_off_light_val)),
            is_openwdr=is_open_wdr,
            is_openhdr=is_open_hdr,
        )

    async def _async_update_data(self) -> FoscamDeviceInfo:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.hass.async_add_executor_job(self.gather_all_configs)
