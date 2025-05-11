"""DataUpdateCoordinator for the IRM KMI integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Any

from irm_kmi_api import IrmKmiApiError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.dt import utcnow

from .const import DOMAIN, IRM_KMI_NAME, OUT_OF_BENELUX
from .data import IrmKmiConfigEntry, ProcessedCoordinatorData
from .utils import disable_from_config, get_config_value, preferred_language

_LOGGER = logging.getLogger(__name__)


class IrmKmiCoordinator(TimestampDataUpdateCoordinator):
    """Coordinator to update data from IRM KMI."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            # Name of the data. For logging purposes.
            name="IRM KMI weather",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=7),
        )
        self.config_entry: IrmKmiConfigEntry = entry
        self._api = entry.runtime_data
        self._zone = get_config_value(entry, CONF_ZONE)
        self.shared_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=IRM_KMI_NAME.get(
                preferred_language(self.hass, self.config_entry)
            ),
            name=f"{entry.title}",
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables so entities can quickly look up their data.
        :return: ProcessedCoordinatorData
        """
        # When integration is set up, set the logging level of the irm_kmi_api package to the same level to help debugging.
        logging.getLogger("irm_kmi_api").setLevel(_LOGGER.getEffectiveLevel())

        self._api.expire_cache()
        if (zone := self.hass.states.get(self._zone)) is None:
            raise UpdateFailed(f"Zone '{self._zone}' not found")
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already handled by the data update coordinator.
            async with asyncio.timeout(60):
                await self._api.refresh_forecasts_coord(
                    {
                        "lat": zone.attributes[ATTR_LATITUDE],
                        "long": zone.attributes[ATTR_LONGITUDE],
                    }
                )

        except IrmKmiApiError as err:
            if (
                self.last_update_success_time is not None
                and self.update_interval is not None
                and self.last_update_success_time - utcnow()
                < timedelta(seconds=2.5 * self.update_interval.seconds)
            ):
                _LOGGER.warning(
                    "Error communicating with API for general forecast: %s. Keeping the old data",
                    err,
                )
                return self.data
            raise UpdateFailed(
                f"Error communicating with API for general forecast: {err}. "
                f"Last success time is: {self.last_update_success_time}"
            ) from err

        if self._api.get_city() in OUT_OF_BENELUX:
            _LOGGER.error(
                "The zone %s is now out of Benelux and forecast is only available in Benelux. "
                "Associated device is now disabled.  Move the zone back in Benelux and re-enable to fix "
                "this",
                self._zone,
            )
            disable_from_config(self.hass, self.config_entry)

            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "zone_moved",
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="zone_moved",
                data={
                    "config_entry_id": self.config_entry.entry_id,
                    "zone": self._zone,
                },
                translation_placeholders={"zone": self._zone},
            )
            return ProcessedCoordinatorData()

        return await self.process_api_data()

    async def async_refresh(self) -> None:
        """Refresh data and log errors."""
        await self._async_refresh(log_failures=True, raise_on_entry_error=True)

    async def process_api_data(self) -> ProcessedCoordinatorData:
        """From the API data, create the object that will be used in the entities."""
        tz = await dt_util.async_get_time_zone("Europe/Brussels")
        lang = preferred_language(self.hass, self.config_entry)

        return ProcessedCoordinatorData(
            current_weather=self._api.get_current_weather(tz),
            daily_forecast=self._api.get_daily_forecast(tz, lang),
            hourly_forecast=self._api.get_hourly_forecast(tz),
            country=self._api.get_country(),
        )
