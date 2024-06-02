"""DataUpdateCoordinator for Ista EcoTrend integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyecotrend_ista.exception_classes import (
    InternalServerError,
    KeycloakError,
    LoginError,
    ServerError,
)
from pyecotrend_ista.pyecotrend_ista import PyEcotrendIsta
from requests.exceptions import RequestException

from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IstaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Ista EcoTrend data update coordinator."""

    details: dict[str, Any]

    def __init__(self, hass: HomeAssistant, ista: PyEcotrendIsta) -> None:
        """Initialize ista EcoTrend data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.ista = ista
        self.details = {}

    async def _async_update_data(self):
        data: dict[str, Any] = {}
        if not self.details:
            try:
                result = await self.hass.async_add_executor_job(
                    self.ista.get_consumption_unit_details
                )
            except (
                ServerError,
                InternalServerError,
                RequestException,
                TimeoutError,
            ) as e:
                raise UpdateFailed(
                    "Unable to connect and retrieve data from ista EcoTrend, try again later"
                ) from e
            except (LoginError, KeycloakError) as e:
                raise HomeAssistantError(
                    f"Authentication failed for {self.ista._email}, check your login credentials"  # noqa: SLF001
                ) from e
            else:
                self.details = {
                    consumption_unit: next(
                        details
                        for details in result["consumptionUnits"]
                        if details["id"] == consumption_unit
                    )
                    for consumption_unit in self.ista.getUUIDs()
                }

        try:
            for consumption_unit in self.ista.getUUIDs():
                data[consumption_unit] = await self.hass.async_add_executor_job(
                    self.ista.get_raw
                )
        except (ServerError, InternalServerError, RequestException, TimeoutError) as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from ista EcoTrend, try again later"
            ) from e
        except (LoginError, KeycloakError) as e:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_exception",
                translation_placeholders={CONF_EMAIL: self.ista._email},  # noqa: SLF001
            ) from e

        return data
