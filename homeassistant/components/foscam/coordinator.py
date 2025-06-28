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
        is_openIr = infra_led_config["mode"] if ret_ir == 0 and infra_led_config else 0

        ret_mf, mirror_flip_setting = self.session.get_mirror_and_flip_setting()
        is_Flip = (
            mirror_flip_setting["isFlip"] if ret_mf == 0 and mirror_flip_setting else 0
        )
        is_Mirror = (
            mirror_flip_setting["isMirror"]
            if ret_mf == 0 and mirror_flip_setting
            else 0
        )

        ret_sleep, sleep_setting = self.session.is_asleep()
        is_asleep = {"supported": ret_sleep == 0, "status": sleep_setting}

        ret_wl, is_openWhiteLight = self.session.getWhiteLightBrightness()
        is_openWhiteLight_val = (
            is_openWhiteLight["enable"] if ret_wl == 0 and is_openWhiteLight else 0
        )

        ret_sc, is_sirenalarm = self.session.getSirenConfig()
        is_sirenalarm_val = (
            is_sirenalarm["sirenEnable"] if ret_sc == 0 and is_sirenalarm else 0
        )

        ret_vol, Volume = self.session.getAudioVolume()
        Volume_val = Volume["volume"] if ret_vol == 0 and Volume else 0

        ret_sv, SpeakVolume = self.session.getSpeakVolume()
        SpeakVolume_val = (
            SpeakVolume["SpeakVolume"] if ret_sv == 0 and SpeakVolume else 0
        )

        ret_ves, is_TurnOffVolume = self.session.getVoiceEnableState()
        is_TurnOffVolume_val = (
            0 if (ret_ves == 0 and int(is_TurnOffVolume["isEnable"]) == 1) else 1
        )

        ret_les, is_TurnOffLight = self.session.getLedEnableState()
        is_TurnOffLight_val = (
            0 if (ret_les == 0 and int(is_TurnOffLight["isEnable"]) == 1) else 1
        )

        is_OpenWdr = None
        is_OpenHdr = None
        if ((1 << 8) & int(product_info.get("reserve3", "0"))) != 0:
            ret_wdr, is_OpenWdr_data = self.session.getWdrMode()
            is_OpenWdr = (
                is_OpenWdr_data["mode"] if ret_wdr == 0 and is_OpenWdr_data else None
            )
        else:
            ret_hdr, is_OpenHdr_data = self.session.getHdrMode()
            is_OpenHdr = (
                is_OpenHdr_data["mode"] if ret_hdr == 0 and is_OpenHdr_data else None
            )

        return FoscamDeviceInfo(
            dev_info=dev_info,
            product_info=product_info,
            is_openir=bool(is_openIr),
            is_flip=bool(is_Flip),
            is_mirror=bool(is_Mirror),
            is_asleep=is_asleep,
            is_openwhitelight=bool(is_openWhiteLight_val),
            is_sirenalarm=bool(is_sirenalarm_val),
            volume=Volume_val,
            speakvolume=SpeakVolume_val,
            is_turnoffvolume=bool(is_TurnOffVolume_val),
            is_turnofflight=bool(is_TurnOffLight_val),
            is_openwdr=bool(is_OpenWdr),
            is_openhdr=bool(is_OpenHdr),
        )

    async def _async_update_data(self) -> FoscamDeviceInfo:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.hass.async_add_executor_job(self.gather_all_configs)
