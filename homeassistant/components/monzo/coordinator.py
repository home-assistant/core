"""The Monzo integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from pprint import pformat
from typing import TYPE_CHECKING, Any, override

from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticatedMonzoAPI
from .const import DOMAIN

if TYPE_CHECKING:
    from .webhook import MonzoWebhookManager

_LOGGER = logging.getLogger(__name__)


@dataclass
class MonzoData:
    """A dataclass for holding sensor data returned by the DataUpdateCoordinator."""

    accounts: dict[str, dict[str, Any]]
    pots: dict[str, dict[str, Any]]


class MonzoCoordinator(DataUpdateCoordinator[MonzoData]):
    """Class to manage fetching Monzo data from the API."""

    config_entry: MonzoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MonzoConfigEntry,
        api: AuthenticatedMonzoAPI,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.api = api

    @override
    async def _async_update_data(self) -> MonzoData:
        """Fetch data from Monzo API."""
        try:
            accounts = await self.api.user_account.accounts()
            pots = await self.api.user_account.pots()
        except AuthorisationExpiredError as err:
            raise ConfigEntryAuthFailed from err
        except InvalidMonzoAPIResponseError as err:
            message = "Invalid Monzo API response."
            translation_key = "invalid_api_response"
            if err.missing_key:
                _LOGGER.debug(
                    "%s\nMissing key: %s\nResponse:\n%s",
                    message,
                    err.missing_key,
                    pformat(err.response),
                )
                translation_key = "invalid_api_response_with_details"
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key=translation_key,
            ) from err

        data = MonzoData(
            accounts={account["id"]: account for account in accounts},
            pots={pot["id"]: pot for pot in pots},
        )
        current_resource_ids = data.accounts.keys() | data.pots.keys()
        device_registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        ):
            resource_ids = {
                identifier[1]
                for identifier in device.identifiers
                if identifier[0] == DOMAIN
            }
            if resource_ids and resource_ids.isdisjoint(current_resource_ids):
                device_registry.async_remove_device(device.id)

        return data


@dataclass
class MonzoRuntimeData:
    """Runtime data for a Monzo config entry."""

    coordinator: MonzoCoordinator
    webhook_manager: MonzoWebhookManager


type MonzoConfigEntry = ConfigEntry[MonzoRuntimeData]
