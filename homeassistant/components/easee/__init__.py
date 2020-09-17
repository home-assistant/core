"""Easee charger component."""
import asyncio
from datetime import timedelta
import logging
from typing import List

from easee import Easee, Site
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_validation as cv,
    device_registry,
)
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import EaseeConfigFlow  # noqa
from .const import (
    CONF_MONITORED_SITES,
    DOMAIN,
    EASEE_ENTITIES,
    LISTENER_FN_CLOSE,
    MEASURED_CONSUMPTION_DAYS,
    PLATFORMS,
    SCAN_INTERVAL_SECONDS,
)
from .entity import ChargerData, ChargersData

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=SCAN_INTERVAL_SECONDS)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_MONITORED_CONDITIONS, default=["status"]): vol.All(
                    cv.ensure_list, [vol.In(EASEE_ENTITIES)]
                ),
                vol.Optional(MEASURED_CONSUMPTION_DAYS, default=[]): vol.All(
                    cv.ensure_list
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Easee integration component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Easee integration from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    client_session = aiohttp_client.async_get_clientsession(hass)
    easee = Easee(username, password, client_session)
    sites: List[Site] = await easee.get_sites()

    hass.data[DOMAIN]["session"] = easee
    hass.data[DOMAIN]["config"] = entry
    hass.data[DOMAIN]["sites"] = sites
    hass.data[DOMAIN]["circuits"] = []
    hass.data[DOMAIN]["chargers"] = []
    entities = []
    charger_data_list = []
    all_sites = []

    for site in sites:
        all_sites.append(site["name"])
    config = hass.data[DOMAIN]["config"]
    monitored_sites = config.options.get(CONF_MONITORED_SITES, all_sites)

    for site in sites:
        if not site["name"] in monitored_sites:
            _LOGGER.debug("Found site (unmonitored): %s %s", site.id, site["name"])
        else:
            _LOGGER.debug("Found site (monitored): %s %s", site.id, site["name"])
            for circuit in site.get_circuits():
                _LOGGER.debug("Found circuit: %s %s", circuit.id, circuit["panelName"])
                hass.data[DOMAIN]["circuits"].append(circuit)
                for charger in circuit.get_chargers():
                    _LOGGER.debug("Found charger: %s %s", charger.id, charger.name)
                    hass.data[DOMAIN]["chargers"].append(charger)
                    charger_data = ChargerData(charger, circuit, site)
                    charger_data_list.append(charger_data)

    chargers_data = ChargersData(charger_data_list, entities)
    hass.data[DOMAIN]["chargers_data"] = chargers_data

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    hass.async_add_job(chargers_data.async_refresh)
    async_track_time_interval(hass, chargers_data.async_refresh, SCAN_INTERVAL)

    undo_listener = entry.add_update_listener(config_entry_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        LISTENER_FN_CLOSE: undo_listener,
    }
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
        hass.data[DOMAIN][entry.entry_id][LISTENER_FN_CLOSE]()
        hass.data[DOMAIN] = {}

    return unload_ok


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update, delete device and set it up again as suggested on discord #devs_core."""
    await hass.config_entries.async_reload(entry.entry_id)

    dev_reg = await device_registry.async_get_registry(hass)
    devices_to_purge = []
    for device in dev_reg.devices.values():
        for identifier in device.identifiers:
            if DOMAIN in identifier:
                devices_to_purge.append(device.id)

    _LOGGER.debug("Purging device: %s", devices_to_purge)
    for device_id in devices_to_purge:
        dev_reg.async_remove_device(device_id)
