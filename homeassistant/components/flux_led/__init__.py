"""The Flux LED/MagicLight integration."""
import asyncio
from datetime import timedelta
import logging

from flux_led import BulbScanner
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BULB_COORDINATOR,
    DEFAULT_NETWORK_SCAN_INTERVAL,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Flux LED/MagicLight component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Flux LED/MagicLight from a config entry."""

    conf = entry.data

    if conf[CONF_TYPE] == "auto":
        scanner_api = BulbScanner()
        if len(scanner_api.scan()) == 0:
            raise PlatformNotReady("No FluxLED/MagicHome Bulbs found in network.")
            return False

        coordinator = FluxLEDListUpdateCoordinator(
            hass=hass,
            name="flux_led_scanner",
            update_interval=DEFAULT_NETWORK_SCAN_INTERVAL,
        )

        await coordinator.async_refresh()

        if not coordinator.last_update_success:
            raise ConfigEntryNotReady

        hass.data[DOMAIN][entry.entry_id] = {
            CONF_TYPE: "auto",
            BULB_COORDINATOR: coordinator,
        }

    else:
        hass.data[DOMAIN][entry.entry_id] = {
            CONF_TYPE: "manual",
            CONF_NAME: conf[CONF_NAME],
            CONF_HOST: conf[CONF_HOST],
            BULB_COORDINATOR: None,
        }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FluxLEDListUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from flux_led bulbs on the network."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_interval: int,
    ):
        """Initialize the update coordinator."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=name,
            update_interval=timedelta(seconds=update_interval),
        )

        self._known_bulbs = {}

    async def _async_update_data(self):
        """Fetch data from the network for flux_leds."""
        bulb_scan = BulbScanner()

        bulb_list = bulb_scan.scan()

        for bulb in bulb_list:
            if bulb["id"] not in self._known_bulbs:
                bulb["active"] = True
                self._known_bulbs[bulb["id"]] = bulb
                async_dispatcher_send(self.hass, SIGNAL_ADD_DEVICE, bulb)
            else:
                self._known_bulbs[bulb["id"]]["ipaddr"] = bulb["ipaddr"]
                self._known_bulbs[bulb["id"]]["active"] = True

        for bulb_id, bulb in self._known_bulbs.items():
            if bulb not in bulb_list:
                self._known_bulbs[bulb_id]["active"] = False

        return self._known_bulbs
