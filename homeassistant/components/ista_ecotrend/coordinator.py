"""DataUpdateCoordinator for Ista EcoTrend integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyecotrend_ista import KeycloakError, LoginError, PyEcotrendIsta, ServerError

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IstaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Ista EcoTrend data update coordinator."""

    def __init__(self, hass: HomeAssistant, ista: PyEcotrendIsta) -> None:
        """Initialize ista EcoTrend data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.ista = ista
        self.details: dict[str, Any] = {}

    async def _async_update_data(self):
        """Fetch ista EcoTrend data."""

        if not self.details:
            self.details = await self.async_get_details()

        try:
            return await self.hass.async_add_executor_job(self.get_consumption_data)
        except ServerError as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from ista EcoTrend, try again later"
            ) from e
        except (LoginError, KeycloakError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_exception",
                translation_placeholders={CONF_EMAIL: self.ista._email},  # noqa: SLF001
            ) from e

    def get_consumption_data(self) -> dict[str, Any]:
        """Get raw json data for all consumption units."""

        return {
            consumption_unit: self.ista.get_consumption_data(consumption_unit)
            for consumption_unit in self.ista.get_uuids()
        }

    async def async_get_details(self) -> dict[str, Any]:
        """Retrieve details of consumption units."""
        try:
            result = await self.hass.async_add_executor_job(
                self.ista.get_consumption_unit_details
            )
        except ServerError as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from ista EcoTrend, try again later"
            ) from e
        except (LoginError, KeycloakError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_exception",
                translation_placeholders={CONF_EMAIL: self.ista._email},  # noqa: SLF001
            ) from e
        else:
            return {
                consumption_unit: next(
                    details
                    for details in result["consumptionUnits"]
                    if details["id"] == consumption_unit
                )
                for consumption_unit in self.ista.get_uuids()
            }
