"""The DirecTV integration."""
import asyncio
from datetime import timedelta
from typing import Any, Dict

from directv import DIRECTV, DIRECTVError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_SOFTWARE_VERSION,
    ATTR_VIA_DEVICE,
    DOMAIN,
)

CONFIG_SCHEMA = cv.deprecated(DOMAIN, invalidation_version="0.120")

PLATFORMS = ["media_player", "remote"]
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the DirecTV component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DirecTV from a config entry."""
    dtv = DIRECTV(entry.data[CONF_HOST], session=async_get_clientsession(hass))

    try:
        await dtv.update()
    except DIRECTVError as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = dtv

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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


class DIRECTVEntity(Entity):
    """Defines a base DirecTV entity."""

    def __init__(self, *, dtv: DIRECTV, name: str, address: str = "0") -> None:
        """Initialize the DirecTV entity."""
        self._address = address
        self._device_id = address if address != "0" else dtv.device.info.receiver_id
        self._is_client = address != "0"
        self._name = name
        self.dtv = dtv

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about this DirecTV receiver."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._device_id)},
            ATTR_NAME: self.name,
            ATTR_MANUFACTURER: self.dtv.device.info.brand,
            ATTR_MODEL: None,
            ATTR_SOFTWARE_VERSION: self.dtv.device.info.version,
            ATTR_VIA_DEVICE: (DOMAIN, self.dtv.device.info.receiver_id),
        }
