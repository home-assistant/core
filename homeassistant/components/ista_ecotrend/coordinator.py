"""DataUpdateCoordinator for Ista EcoTrend integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyecotrend_ista import KeycloakError, LoginError, PyEcotrendIsta, ServerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type IstaConfigEntry = ConfigEntry[IstaCoordinator]


class IstaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Ista EcoTrend data update coordinator."""

    config_entry: IstaConfigEntry
    details: dict[str, Any]

    def __init__(
        self, hass: HomeAssistant, config_entry: IstaConfigEntry, ista: PyEcotrendIsta
    ) -> None:
        """Initialize ista EcoTrend data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.ista = ista

    async def _async_setup(self) -> None:
        """Set up the ista EcoTrend coordinator."""

        try:
            self.details = await self.hass.async_add_executor_job(self.get_details)
        except ServerError as e:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connection_exception",
            ) from e
        except (LoginError, KeycloakError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_exception",
                translation_placeholders={
                    CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                },
            ) from e

    async def _async_update_data(self):
        """Fetch ista EcoTrend data."""

        try:
            return await self.hass.async_add_executor_job(self.get_consumption_data)
        except ServerError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_exception",
            ) from e
        except (LoginError, KeycloakError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_exception",
                translation_placeholders={
                    CONF_EMAIL: self.config_entry.data[CONF_EMAIL]
                },
            ) from e

    def get_consumption_data(self) -> dict[str, Any]:
        """Get raw json data for all consumption units."""

        self.ista.login()
        return {
            consumption_unit: self.ista.get_consumption_data(consumption_unit)
            for consumption_unit in self.ista.get_uuids()
        }

    def get_details(self) -> dict[str, Any]:
        """Retrieve details of consumption units."""

        self.ista.login()
        result = self.ista.get_consumption_unit_details()

        return {
            consumption_unit: next(
                details
                for details in result["consumptionUnits"]
                if details["id"] == consumption_unit
            )
            for consumption_unit in self.ista.get_uuids()
        }
