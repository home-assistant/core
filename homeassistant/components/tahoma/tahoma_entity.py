"""Parent class for every Somfy TaHoma device."""
import logging
from typing import Any, Dict

from pyhoma.models import Device

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TahomaDataUpdateCoordinator
from .overkiz_executor import OverkizExecutor

ATTR_RSSI_LEVEL = "rssi_level"

CORE_AVAILABILITY_STATE = "core:AvailabilityState"
CORE_MANUFACTURER_NAME_STATE = "core:ManufacturerNameState"
CORE_MODEL_STATE = "core:ModelState"
CORE_STATUS_STATE = "core:StatusState"


_LOGGER = logging.getLogger(__name__)


class TahomaEntity(CoordinatorEntity, Entity):
    """Representation of a TaHoma device entity."""

    def __init__(self, device_url: str, coordinator: TahomaDataUpdateCoordinator):
        """Initialize the device."""
        super().__init__(coordinator)
        self.device_url = device_url
        self.executor = OverkizExecutor(device_url, coordinator)

    @property
    def device(self) -> Device:
        """Return TaHoma device linked to this entity."""
        return self.coordinator.data[self.device_url]

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.device.label

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.device.available

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.device.deviceurl

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return not self.device.states

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device registry information for this entity."""
        manufacturer = (
            self.executor.select_state(CORE_MANUFACTURER_NAME_STATE) or "Somfy"
        )
        model = self.executor.select_state(CORE_MODEL_STATE) or self.device.widget

        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": manufacturer,
            "name": self.name,
            "model": model,
            "sw_version": self.device.controllable_name,
        }
