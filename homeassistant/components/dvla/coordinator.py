"""DVLA Coordinator."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from aio_dvla_vehicle_enquiry import (
    DVLAAuthError,
    DVLAClient,
    DVLAError,
    DVLAInvalidRegistrationError,
    DVLARateLimitError,
)
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_KEY, CONF_REG_NUMBER, DOMAIN

if TYPE_CHECKING:
    from . import DVLAConfigEntry

_LOGGER = logging.getLogger(__name__)
_RETRY_AFTER = 3600


class DVLACoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Data coordinator."""

    config_entry: DVLAConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: DVLAConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(weeks=1),
        )
        self.client = DVLAClient(session, API_KEY)
        self.reg_number = config_entry.data[CONF_REG_NUMBER]

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch vehicle data from the DVLA API."""
        try:
            return await self.client.async_get_vehicle(self.reg_number)
        except DVLAInvalidRegistrationError:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="vehicle_not_found",
                translation_placeholders={"reg_number": self.reg_number},
            ) from None
        except DVLAAuthError:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from None
        except DVLARateLimitError:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="rate_limited",
                retry_after=_RETRY_AFTER,
            ) from None
        except DVLAError:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                retry_after=_RETRY_AFTER
                if self.config_entry.state is ConfigEntryState.LOADED
                else None,
            ) from None
