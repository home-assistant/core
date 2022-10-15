"""The pvpc_hourly_pricing integration to collect Spain official electric prices."""
from collections.abc import Mapping
from datetime import datetime, timedelta
import logging

from aiopvpc import DEFAULT_POWER_KW, TARIFFS, PVPCData
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
    async_get,
    async_migrate_entries,
)
from homeassistant.helpers.typing import ConfigType
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
CONFIG_SCHEMA = vol.Schema(
    vol.All(cv.deprecated(DOMAIN), {DOMAIN: cv.ensure_list(UI_CONFIG_SCHEMA)}),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the electricity price sensor from configuration.yaml."""
    for conf in config.get(DOMAIN, []):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, data=conf, context={"source": SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up pvpc hourly pricing from a config entry."""
    if len(entry.data) == 2:
        defaults = {
            ATTR_TARIFF: _DEFAULT_TARIFF,
            ATTR_POWER: DEFAULT_POWER_KW,
            ATTR_POWER_P3: DEFAULT_POWER_KW,
        }
        data = {**entry.data, **defaults}
        hass.config_entries.async_update_entry(
            entry, unique_id=_DEFAULT_TARIFF, data=data, options=defaults
        )

        @callback
        def update_unique_id(reg_entry):
            """Change unique id for sensor entity, pointing to new tariff."""
            return {"new_unique_id": _DEFAULT_TARIFF}

        try:
            await async_migrate_entries(hass, entry.entry_id, update_unique_id)
            _LOGGER.warning(
                "Migrating PVPC sensor from old tariff '%s' to new '%s'. "
                "Configure the integration to set your contracted power, "
                "and select prices for Ceuta/Melilla, "
                "if that is your case",
                entry.data[ATTR_TARIFF],
                _DEFAULT_TARIFF,
            )
        except ValueError:
            # there were multiple sensors (with different old tariffs, up to 3),
            # so we leave just one and remove the others
            ent_reg: EntityRegistry = async_get(hass)
            for entity_id, reg_entry in ent_reg.entities.items():
                if reg_entry.config_entry_id == entry.entry_id:
                    ent_reg.async_remove(entity_id)
                    _LOGGER.warning(
                        "Old PVPC Sensor %s is removed "
                        "(another one already exists, using the same tariff)",
                        entity_id,
                    )
                    break

            await hass.config_entries.async_remove(entry.entry_id)
            return False

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
        for attrib in (ATTR_TARIFF, ATTR_POWER, ATTR_POWER_P3)
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


class ElecPricesDataUpdateCoordinator(DataUpdateCoordinator[Mapping[datetime, float]]):
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

    async def _async_update_data(self) -> Mapping[datetime, float]:
        """Update electricity prices from the ESIOS API."""
        prices = await self.api.async_update_prices(dt_util.utcnow())
        self.api.process_state_and_attributes(dt_util.utcnow())
        if not prices:
            raise UpdateFailed

        return prices
