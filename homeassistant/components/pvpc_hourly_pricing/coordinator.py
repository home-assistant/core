"""The pvpc_hourly_pricing integration to collect Spain official electric prices."""

from datetime import timedelta
import logging

from aiopvpc import BadApiTokenAuthError, EsiosApiData, PVPCData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import ATTR_POWER, ATTR_POWER_P3, ATTR_TARIFF, DOMAIN

_LOGGER = logging.getLogger(__name__)

type PVPCConfigEntry = ConfigEntry[ElecPricesDataUpdateCoordinator]


class ElecPricesDataUpdateCoordinator(DataUpdateCoordinator[EsiosApiData]):
    """Class to manage fetching Electricity prices data from API."""

    config_entry: PVPCConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: PVPCConfigEntry, sensor_keys: set[str]
    ) -> None:
        """Initialize."""
        config = entry.data.copy()
        config.update({attr: value for attr, value in entry.options.items() if value})

        self.api = PVPCData(
            session=async_get_clientsession(hass),
            tariff=config[ATTR_TARIFF],
            local_timezone=hass.config.time_zone,
            power=config[ATTR_POWER],
            power_valley=config[ATTR_POWER_P3],
            api_token=config.get(CONF_API_TOKEN),
            sensor_keys=tuple(sensor_keys),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
        )

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self.config_entry.entry_id

    async def _async_update_data(self) -> EsiosApiData:
        """Update electricity prices from the ESIOS API."""
        requested_at = dt_util.utcnow()
        try:
            api_data = await self.api.async_update_all(self.data, requested_at)
        except KeyError as err:
            missing_key = err.args[0] if err.args else None
            if missing_key in (requested_at.year, str(requested_at.year)):
                raise UpdateFailed(
                    f"PVPC data is not available for requested year {requested_at.year}"
                ) from err
            raise UpdateFailed(
                f"Unexpected PVPC data lookup failure: missing key {missing_key!r}"
            ) from err
        except BadApiTokenAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        if (
            not api_data
            or not api_data.sensors
            or not any(api_data.availability.values())
        ):
            raise UpdateFailed
        return api_data
