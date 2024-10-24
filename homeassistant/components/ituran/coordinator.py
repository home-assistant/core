"""Coordinator for Ituran."""

from datetime import timedelta
import logging

from pyituran import Ituran, Vehicle
from pyituran.exceptions import IturanApiError, IturanAuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ID_OR_PASSPORT, CONF_MOBILE_ID, CONF_PHONE_NUMBER, DOMAIN

_LOGGER = logging.getLogger(__name__)


class IturanDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Vehicle]]):
    """Class to manage fetching Ituran data."""

    ituran: Ituran

    def __init__(self, hass: HomeAssistant, *, entry: ConfigEntry) -> None:
        """Initialize account-wide BMW data updater."""
        self.ituran = Ituran(
            entry.data[CONF_ID_OR_PASSPORT],
            entry.data[CONF_PHONE_NUMBER],
            entry.data[CONF_MOBILE_ID],
        )
        self._entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry.data[CONF_ID_OR_PASSPORT]}",
            update_interval=timedelta(seconds=300),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Vehicle]:
        """Fetch data from Ituran."""

        try:
            vehicles = await self.ituran.get_vehicles()
        except IturanApiError as e:
            raise UpdateFailed(e) from e
        except IturanAuthError as e:
            raise ConfigEntryAuthFailed(e) from e

        updated_data = {vehicle.license_plate: vehicle for vehicle in vehicles}
        self._cleanup_removed_vehicles(updated_data)

        return updated_data

    def _cleanup_removed_vehicles(self, data: dict[str, Vehicle]) -> None:
        account_vehicles = {(DOMAIN, license_plate) for license_plate in data}
        device_registry = dr.async_get(self.hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=self._entry.entry_id
        )
        for device in device_entries:
            if not device.identifiers.intersection(account_vehicles):
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=self._entry.entry_id
                )
