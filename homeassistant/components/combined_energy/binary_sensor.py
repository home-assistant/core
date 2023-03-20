"""Binary sensor for current connectivity status of Combined Energy hub."""
from __future__ import annotations

from combined_energy import CombinedEnergy

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_API_CLIENT, DOMAIN, SENSOR_DESCRIPTION_CONNECTED
from .coordinator import CombinedEnergyConnectivityDataService


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""

    api: CombinedEnergy = hass.data[DOMAIN][entry.entry_id][DATA_API_CLIENT]

    # Initialise service
    connection = CombinedEnergyConnectivityDataService(hass, api)
    connection.async_setup()
    await connection.coordinator.async_refresh()

    async_add_entities([CombinedEnergyConnectedSensor(entry.title, connection)])


class CombinedEnergyConnectedSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Combined Energy connection status sensor."""

    data_service: CombinedEnergyConnectivityDataService

    def __init__(
        self, entry_title: str, data_service: CombinedEnergyConnectivityDataService
    ) -> None:
        """Initialise Connected Sensor."""
        super().__init__(data_service.coordinator)

        self.data_service = data_service
        self.entity_description = SENSOR_DESCRIPTION_CONNECTED

        self._attr_name = f"{entry_title} {self.entity_description.name}"
        self._attr_unique_id = f"install_{self.data_service.api.installation_id}-{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        if self.data_service.data is not None:
            return self.data_service.data.connected
        return None
