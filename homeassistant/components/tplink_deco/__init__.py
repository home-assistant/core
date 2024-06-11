"""Support for TP-Link Deco routers."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PLATFORMS, KEY_ROUTER, KEY_COORDINATOR_STATUS
from .errors import CannotLoginException
from .router import TPLinkDecoRouter

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TP-Link Deco component."""
    router = TPLinkDecoRouter(hass, entry)
    try:
        if not await router.async_setup():
            raise ConfigEntryNotReady
    except CannotLoginException as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})

    async def async_update_status() -> dict[str, Any] | None:
        """Fetch status from the router."""
        return await router.async_get_status()

    coordinator_status = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{router.device_name} Status",
        update_method=async_update_status,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator_status.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_ROUTER: router,
        KEY_COORDINATOR_STATUS: coordinator_status,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok
