"""The foscam coordinator object."""

import asyncio
from datetime import timedelta
from typing import Any

from libpyfoscam import FoscamCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER

type FoscamConfigEntry = ConfigEntry[FoscamCoordinator]


class FoscamCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Foscam coordinator."""

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

    def gather_all_configs(self):
        """Get all Foscam configurations."""
        configs = {}

        ret, dev_info = self.session.get_dev_info()
        configs["dev_info"] = dev_info

        ret, all_info = self.session.get_product_all_info()
        configs["product_info"] = all_info

        ret, infra_led_config = self.session.get_infra_led_config()
        configs["is_openIr"] = infra_led_config["mode"]

        ret, mirror_flip_setting = self.session.get_mirror_and_flip_setting()
        configs["is_Flip"] = mirror_flip_setting["isFlip"]
        configs["is_Mirror"] = mirror_flip_setting["isMirror"]

        ret, sleep_setting = self.session.is_asleep()
        configs["is_asleep"] = {"supported": ret == 0, "status": sleep_setting}

        ret, is_openWhiteLight = self.session.getWhiteLightBrightness()
        configs["is_openWhiteLight"] = is_openWhiteLight["enable"]

        ret, is_sirenalarm = self.session.getSirenConfig()
        configs["is_sirenalarm"] = is_sirenalarm["sirenEnable"]

        ret, Volume = self.session.getAudioVolume()
        configs["Volume"] = Volume["volume"]

        ret, SpeakVolume = self.session.getSpeakVolume()
        configs["SpeakVolume"] = SpeakVolume["SpeakVolume"]

        ret, is_TurnOffVolume = self.session.getVoiceEnableState()
        configs["is_TurnOffVolume"] = 0 if int(is_TurnOffVolume["isEnable"]) == 1 else 1

        ret, is_TurnOffLight = self.session.getLedEnableState()
        configs["is_TurnOffLight"] = 0 if int(is_TurnOffLight["isEnable"]) == 1 else 1
        if ((1 << 8) & int(all_info["reserve3"])) != 0:
            ret, is_OpenWdr = self.session.getWdrMode()
            configs["is_OpenWdr"] = is_OpenWdr["mode"]
        else:
            ret, is_OpenHdr = self.session.getHdrMode()
            configs["is_OpenHdr"] = is_OpenHdr["mode"]
        return configs

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        async with asyncio.timeout(30):
            return await self.hass.async_add_executor_job(self.gather_all_configs)
