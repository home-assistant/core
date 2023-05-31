"""The pvpc_hourly_pricing integration to collect Spain official electric prices."""
from datetime import timedelta
import logging

from aiopvpc import DEFAULT_POWER_KW, TARIFFS, EsiosApiData, PVPCData
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TARIFF = TARIFFS[0]
VALID_POWER = vol.All(vol.Coerce(float), vol.Range(min=1.0, max=15.0))
VALID_TARIFF = vol.In(TARIFFS)
UI_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(ATTR_TARIFF, default=_DEFAULT_TARIFF): VALID_TARIFF,
        vol.Required(ATTR_POWER, default=DEFAULT_POWER_KW): VALID_POWER,
        vol.Required(ATTR_POWER_P3, default=DEFAULT_POWER_KW): VALID_POWER,
    }
)
CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pvpc hourly pricing from a config entry."""
    coordinator = ElecPricesDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    if any(
        entry.data.get(attrib) != entry.options.get(attrib)
        for attrib in (ATTR_POWER, ATTR_POWER_P3)
    ):
        # update entry replacing data with new options
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, **entry.options}
        )
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class ElecPricesDataUpdateCoordinator(DataUpdateCoordinator[EsiosApiData]):
    """Class to manage fetching Electricity prices data from API."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.api = PVPCData(
            session=async_get_clientsession(hass),
            tariff=entry.data[ATTR_TARIFF],
            local_timezone=hass.config.time_zone,
            power=entry.data[ATTR_POWER],
            power_valley=entry.data[ATTR_POWER_P3],
        )
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=30)
        )
        self._entry = entry

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self._entry.entry_id

    async def _async_update_data(self) -> EsiosApiData:
        """Update electricity prices from the ESIOS API."""
        api_data = await self.api.async_update_all(self.data, dt_util.utcnow())
        if (
            not api_data
            or not api_data.sensors
            or not all(api_data.availability.values())
        ):
            raise UpdateFailed
        return api_data
