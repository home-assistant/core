"""Orange Livebox."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .bridge import BridgeData
from .const import (
    COMPONENTS,
    CONF_LAN_TRACKING,
    COORDINATOR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DOMAIN,
    LIVEBOX_API,
    LIVEBOX_ID,
    UNSUB_LISTENER,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_LAN_TRACKING, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Load configuration for Livebox component."""
    hass.data.setdefault(DOMAIN, {})

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Livebox as config entry."""
    bridge = BridgeData(hass, config_entry)
    try:
        await bridge.async_connect()
    except Exception:  # pylint: disable=broad-except
        return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="livebox",
        update_method=bridge.async_fetch_datas,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise PlatformNotReady

    infos = coordinator.data.get("infos")
    if infos is None:
        return False

    unsub_listener = config_entry.add_update_listener(update_listener)

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, infos.get("SerialNumber"))},
        manufacturer=infos.get("Manufacturer"),
        name=infos.get("ProductClass"),
        model=infos.get("ModelName"),
        sw_version=infos.get("SoftwareVersion"),
    )

    hass.data[DOMAIN][config_entry.entry_id] = {
        LIVEBOX_ID: config_entry.unique_id,
        UNSUB_LISTENER: unsub_listener,
        COORDINATOR: coordinator,
        LIVEBOX_API: bridge.api,
    }

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    async def async_livebox_reboot(call):
        """Handle reboot service call."""
        await bridge.async_reboot()

    hass.services.async_register(DOMAIN, "reboot", async_livebox_reboot)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )

    hass.data[DOMAIN][config_entry.entry_id][UNSUB_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass, config_entry):
    """Reload device tracker if change option."""
    await hass.config_entries.async_reload(config_entry.entry_id)
