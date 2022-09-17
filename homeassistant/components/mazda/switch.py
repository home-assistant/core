"""Platform for Mazda switch integration."""
from pymazda import Client as MazdaAPIClient

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    async_add_entities(
        MazdaChargingSwitch(client, coordinator, index)
        for index, data in enumerate(coordinator.data)
        if data["isElectric"]
    )


class MazdaChargingSwitch(MazdaEntity, SwitchEntity):
    """Class for the charging switch."""

    _attr_name = "Charging"
    _attr_icon = "mdi:ev-station"

    def __init__(
        self,
        client: MazdaAPIClient,
        coordinator: DataUpdateCoordinator,
        index: int,
    ) -> None:
        """Initialize Mazda charging switch."""
        super().__init__(client, coordinator, index)

        self._attr_unique_id = self.vin

    @property
    def is_on(self):
        """Return true if the vehicle is charging."""
        return self.data["evStatus"]["chargeInfo"]["charging"]

    async def refresh_status_and_write_state(self):
        """Request a status update, retrieve it through the coordinator, and write the state."""
        await self.client.refresh_vehicle_status(self.vehicle_id)

        await self.coordinator.async_request_refresh()

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Start charging the vehicle."""
        await self.client.start_charging(self.vehicle_id)

        await self.refresh_status_and_write_state()

    async def async_turn_off(self, **kwargs):
        """Stop charging the vehicle."""
        await self.client.stop_charging(self.vehicle_id)

        await self.refresh_status_and_write_state()
