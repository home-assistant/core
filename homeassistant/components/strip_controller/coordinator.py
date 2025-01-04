"""Based on homeassistant/components/wled/coordinator.py."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER, SCAN_INTERVAL
from .scrpi.sc_rpi import Device as ScRpiDevice, ScRpiClient

# TOD: implement a listen mechanism like in homeassistant/components/wled/coordinator.py


class ScpRpiDataUpdateCoordinator(DataUpdateCoordinator[ScRpiDevice]):
    """Based on class WLEDDataUpdateCoordinator from homeassistant/components/wled/coordinator.py."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
    ) -> None:
        """Initialize global WLED data updater.

        Based on homeassistant/components/wled/coordinator.py
        """
        # self.keep_main_light = entry.options.get(
        #    CONF_KEEP_MAIN_LIGHT, DEFAULT_KEEP_MAIN_LIGHT
        # )
        # self.wled = WLED(entry.data[CONF_HOST], session=async_get_clientsession(hass))

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.scrpi = ScRpiClient(
            entry.data[CONF_URL], session=async_get_clientsession(hass)
        )
