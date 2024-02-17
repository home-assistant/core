"""Coordinator for FYTA integration."""

from datetime import datetime, timedelta
import logging

from fyta_cli.fyta_connector import FytaConnector

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FytaCoordinator(DataUpdateCoordinator):
    """Fyta custom coordinator."""

    def __init__(
        self, hass: HomeAssistant, fyta: FytaConnector, entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""

        super().__init__(
            hass,
            _LOGGER,
            name="FYTA Coordinator",
            update_method=self._async_update_data,
            update_interval=timedelta(seconds=60),
        )

        self.hass = hass
        self.fyta = fyta
        self.config_entry = entry

        self.plant_list: dict[int, str] = {}
        self.access_token = ""
        self.expiration = None
        self._attr_last_update_success = None

    async def _async_update_data(self):
        """Fetch data from API endpoint."""

        if self.access_token == "" or self.expiration < datetime.now():
            await self.renew_authentication()

        data = await self.fyta.update_all_plants()
        data |= {"online": True}

        self.plant_list = self.fyta.plant_list
        data |= {"plant_number": len(self.plant_list)}
        data |= {"email": self.fyta.email}
        data |= {"name": "Fyta Coordinator"}

        self._attr_last_update_success = datetime.now()
        return data

    async def renew_authentication(self) -> bool:
        """Renew access token for FYTA API."""

        await self.fyta.login()

        self.access_token = self.fyta.access_token
        self.expiration = self.fyta.expiration

        return True


class FytaEntity(CoordinatorEntity[FytaCoordinator]):
    """Base Fyta entity."""

    _attr_has_entity_name = True
    plant_id: int

    def __init__(
        self,
        coordinator: FytaCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription | BinarySensorEntityDescription,
        plant_id: int = -1,
    ) -> None:
        """Initialize the Fyta sensor."""
        super().__init__(coordinator)

        if plant_id == -1:
            self._attr_unique_id = f"{entry.entry_id}-{description.key}"
            self._attr_device_info = DeviceInfo(
                manufacturer="Fyta",
                model="Controller",
                identifiers={(DOMAIN, coordinator.data.get("email"))},
                name="Fyta Coordinator ({})".format(coordinator.data.get("email")),
            )
        else:
            self._attr_unique_id = f"{entry.entry_id}-{plant_id}-{description.key}"
            self._attr_device_info = DeviceInfo(
                manufacturer="Fyta",
                model="plant",
                identifiers={(DOMAIN, str(plant_id))},
                name=coordinator.data.get(plant_id).get("name"),
                via_device=(DOMAIN, coordinator.data.get("email")),
                sw_version=coordinator.data.get(plant_id).get("sw_version"),
            )
        self.entity_description = description
        self.plant_id = plant_id
