"""The pvpc_hourly_pricing integration to collect Spain official electric prices."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiopvpc import (
    DEFAULT_POWER_KW,
    BadApiTokenAuthError,
    EsiosApiData,
    PVPCData,
    get_enabled_sensor_keys,
)

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    CONF_USE_API_TOKEN,
    DEFAULT_TARIFF,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


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
    entity_registry = er.async_get(hass)
    if len(entry.data) == 2:
        defaults = {
            ATTR_TARIFF: DEFAULT_TARIFF,
            ATTR_POWER: DEFAULT_POWER_KW,
            ATTR_POWER_P3: DEFAULT_POWER_KW,
            CONF_API_TOKEN: None,
        }
        data = {**entry.data, **defaults}
        hass.config_entries.async_update_entry(
            entry, unique_id=DEFAULT_TARIFF, data=data, options=defaults
        )

        @callback
        def update_unique_id(reg_entry):
            """Change unique id for sensor entity, pointing to new tariff."""
            return {"new_unique_id": DEFAULT_TARIFF}

        try:
            await er.async_migrate_entries(hass, entry.entry_id, update_unique_id)
            _LOGGER.warning(
                (
                    "Migrating PVPC sensor from old tariff '%s' to new '%s'. "
                    "Configure the integration to set your contracted power, "
                    "and select prices for Ceuta/Melilla, "
                    "if that is your case"
                ),
                entry.data[ATTR_TARIFF],
                DEFAULT_TARIFF,
            )
        except ValueError:
            # there were multiple sensors (with different old tariffs, up to 3),
            # so we leave just one and remove the others
            for entity_id, reg_entry in entity_registry.entities.items():
                if reg_entry.config_entry_id == entry.entry_id:
                    entity_registry.async_remove(entity_id)
                    _LOGGER.warning(
                        (
                            "Old PVPC Sensor %s is removed "
                            "(another one already exists, using the same tariff)"
                        ),
                        entity_id,
                    )
                    break

            await hass.config_entries.async_remove(entry.entry_id)
            return False

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    sensor_keys = get_enabled_sensor_keys(
        using_private_api=entry.data.get(CONF_USE_API_TOKEN, False),
        disabled_sensor_ids=[sensor.unique_id for sensor in entries if sensor.disabled],
    )
    coordinator = ElecPricesDataUpdateCoordinator(hass, entry, sensor_keys)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    if any(
        entry.data.get(attrib) != entry.options.get(attrib)
        for attrib in (ATTR_POWER, ATTR_POWER_P3, CONF_USE_API_TOKEN, CONF_API_TOKEN)
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

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, sensor_keys: set[str]
    ) -> None:
        """Initialize."""
        api_token = None
        if entry.data.get(CONF_USE_API_TOKEN, False):
            api_token = entry.data.get(CONF_API_TOKEN)
        self.api = PVPCData(
            session=async_get_clientsession(hass),
            tariff=entry.data[ATTR_TARIFF],
            local_timezone=hass.config.time_zone,
            power=entry.data[ATTR_POWER],
            power_valley=entry.data[ATTR_POWER_P3],
            api_token=api_token,
            sensor_keys=tuple(sensor_keys),
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
        try:
            api_data = await self.api.async_update_all(self.data, dt_util.utcnow())
        except BadApiTokenAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        if (
            not api_data
            or not api_data.sensors
            or not all(api_data.availability.values())
        ):
            raise UpdateFailed
        return api_data
