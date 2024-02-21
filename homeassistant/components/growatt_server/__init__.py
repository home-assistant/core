"""The Growatt server PV inverter sensor integration."""
from datetime import time
import logging

import const

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .api import get_configured_api
from .plant import get_inverter_list

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Load the saved entities."""

    await hass.config_entries.async_forward_entry_setups(config_entry, const.PLATFORMS)

    def set_grid_first(call: ServiceCall) -> None:
        """Set inverter to export to grid."""

        config = {**config_entry.data}

        api = get_configured_api(hass, config_entry)

        [inverter_list, _] = get_inverter_list(api, config)

        device_sn = inverter_list[0]["deviceSn"]

        sTime1 = call.data.get(const.TIME_SLOT_1_START, time())
        sTime2 = call.data.get(const.TIME_SLOT_2_START, time())
        sTime3 = call.data.get(const.TIME_SLOT_3_START, time())
        eTime1 = call.data.get(const.TIME_SLOT_1_END, time())
        eTime2 = call.data.get(const.TIME_SLOT_2_END, time())
        eTime3 = call.data.get(const.TIME_SLOT_3_END, time())

        schedule_settings = [
            int(call.data[const.DISCHARGE_POWER_RATE]),
            str(call.data[const.DISCHARGE_STOPPED_SOC]),
            f"{sTime1.hour:02d}",
            f"{sTime1.minute:02d}",
            f"{eTime1.hour:02d}",
            f"{eTime1.minute:02d}",
            str(int(call.data[const.TIME_SLOT_1_ENABLED])),
            f"{sTime2.hour:02d}",
            f"{sTime2.minute:02d}",
            f"{eTime2.hour:02d}",
            f"{eTime2.minute:02d}",
            str(int(call.data[const.TIME_SLOT_2_ENABLED])),
            f"{sTime3.hour:02d}",
            f"{sTime3.minute:02d}",
            f"{eTime3.hour:02d}",
            f"{eTime3.minute:02d}",
            str(int(call.data[const.TIME_SLOT_3_ENABLED])),
        ]

        response = api.update_mix_inverter_setting(
            device_sn, "mix_ac_discharge_time_period", schedule_settings
        )

        process_response(response)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, const.PLATFORMS
    )


def process_response(response) -> bool:
    """Process an HTTP response."""

    if not response["success"]:
        _LOGGER.error("Error setting inverter modes")
        return False

    return True
