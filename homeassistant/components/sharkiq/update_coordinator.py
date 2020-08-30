"""Data update coordinator for shark iq vacuums."""

from typing import Dict, List, Set

from async_timeout import timeout
from sharkiqpy import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    SharkIqVacuum,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, LOGGER, UPDATE_INTERVAL


class SharkIqUpdateCoordinator(DataUpdateCoordinator):
    """Define a wrapper class to update Shark IQ data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        ayla_api: AylaApi,
        shark_vacs: List[SharkIqVacuum],
    ) -> None:
        """Set up the SharkIqUpdateCoordinator class."""
        self.ayla_api = ayla_api
        self.shark_vacs: Dict[SharkIqVacuum] = {
            sharkiq.serial_number: sharkiq for sharkiq in shark_vacs
        }
        self._config_entry = config_entry
        self._online_dsns = set()

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    @property
    def online_dsns(self) -> Set[str]:
        """Get the set of all online DSNs."""
        return self._online_dsns

    def device_is_online(self, dsn: str) -> bool:
        """Return the online state of a given vacuum dsn."""
        return dsn in self._online_dsns

    @staticmethod
    async def _async_update_vacuum(sharkiq: SharkIqVacuum) -> None:
        """Asynchronously update the data for a single vacuum."""
        dsn = sharkiq.serial_number
        LOGGER.info("Updating sharkiq data for device DSN %s", dsn)
        with timeout(API_TIMEOUT):
            await sharkiq.async_update()

    async def _async_update_data(self) -> bool:
        """Update data device by device."""
        try:
            all_vacuums = await self.ayla_api.async_list_devices()
            self._online_dsns = {
                v["dsn"]
                for v in all_vacuums
                if v["connection_status"] == "Online" and v["dsn"] in self.shark_vacs
            }

            LOGGER.info("Updating sharkiq data")
            for dsn in self._online_dsns:
                await self._async_update_vacuum(self.shark_vacs[dsn])
        except (
            SharkIqAuthError,
            SharkIqNotAuthedError,
            SharkIqAuthExpiringError,
        ) as err:
            LOGGER.exception("Bad auth state", exc_info=err)
            flow_context = {
                "source": "reauth",
                "unique_id": self._config_entry.unique_id,
            }

            matching_flows = [
                flow
                for flow in self.hass.config_entries.flow.async_progress()
                if flow["context"] == flow_context
            ]

            if not matching_flows:
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_init(
                        DOMAIN, context=flow_context, data=self._config_entry.data,
                    )
                )

            raise UpdateFailed(err)
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.exception("Unexpected error updating SharkIQ", exc_info=err)
            raise UpdateFailed(err)

        return True
