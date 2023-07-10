"""The radiotherm integration base entity."""

from abc import abstractmethod

from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import RadioThermUpdateCoordinator
from .data import RadioThermUpdate


class RadioThermostatEntity(CoordinatorEntity[RadioThermUpdateCoordinator]):
    """Base class for radiotherm entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RadioThermUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.init_data = coordinator.init_data
        self.device = coordinator.init_data.tstat
        self._attr_device_info = DeviceInfo(
            name=self.init_data.name,
            model=self.init_data.model,
            manufacturer="Radio Thermostats",
            sw_version=self.init_data.fw_version,
            connections={(dr.CONNECTION_NETWORK_MAC, self.init_data.mac)},
        )
        self._process_data()

    @property
    def data(self) -> RadioThermUpdate:
        """Returnt the last update."""
        return self.coordinator.data

    @callback
    @abstractmethod
    def _process_data(self) -> None:
        """Update and validate the data from the thermostat."""

    @callback
    def _handle_coordinator_update(self) -> None:
        self._process_data()
        return super()._handle_coordinator_update()
