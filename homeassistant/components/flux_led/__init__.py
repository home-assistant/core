"""The Flux LED/MagicLight integration."""
import copy
from datetime import timedelta
import logging

from flux_led import BulbScanner

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import Throttle

from .const import (
    CONF_AUTOMATIC_ADD,
    DEFAULT_NETWORK_SCAN_INTERVAL,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Flux LED/MagicLight from a config entry."""

    conf = entry.data
    options = entry.options

    if options.get("global", {}).get(CONF_AUTOMATIC_ADD, conf[CONF_AUTOMATIC_ADD]):
        bulb_list = FluxLedList(
            hass,
            devices=conf[CONF_DEVICES],
            config_entry=entry,
        )

        async def schedule_bulb_list_updates(_):
            """Set up scheduled updates for the bulb list."""
            await bulb_list.async_update()

        async_track_time_interval(
            hass,
            schedule_bulb_list_updates,
            timedelta(seconds=DEFAULT_NETWORK_SCAN_INTERVAL),
        )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


class FluxLedList:
    """Class to manage fetching the list of flux_led bulbs on the network."""

    def __init__(
        self, hass: HomeAssistant, devices: dict, config_entry: ConfigEntry
    ) -> None:
        """Initialize the update manager."""

        self.hass = hass
        self._bulb_scan = BulbScanner()
        self._config_entry = config_entry

    @Throttle(timedelta(seconds=DEFAULT_NETWORK_SCAN_INTERVAL))
    async def async_update(self):
        """Fetch data from the network for flux_leds."""
        bulb_list = await self.hass.async_add_executor_job(self._bulb_scan.scan)
        known_bulbs = self._config_entry.data[CONF_DEVICES]
        new_bulbs = {}
        config_data = copy.deepcopy(dict(self._config_entry.data))

        for bulb in bulb_list:
            if bulb["ipaddr"].replace(".", "_") in known_bulbs:
                continue

            new_bulb_id = bulb["ipaddr"].replace(".", "_")
            new_bulb = {
                CONF_HOST: bulb["ipaddr"],
                CONF_NAME: bulb["ipaddr"],
            }

            new_bulbs[new_bulb_id] = new_bulb
            config_data[CONF_DEVICES][new_bulb_id] = new_bulb

        if new_bulbs:
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=config_data
            )

            async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE, new_bulbs)
