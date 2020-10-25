"""Base classes for Renault entities."""
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .pyze_proxy import PyZEVehicleProxy

ATTR_LAST_UPDATE = "last_update"


class RenaultDataEntity(CoordinatorEntity, Entity):
    """Implementation of a Renault entity with a data coordinator."""

    def __init__(self, proxy: PyZEVehicleProxy, entity_type: str, coordinator_key: str):
        """Initialise entity."""
        super().__init__(proxy.coordinators[coordinator_key])
        self.proxy = proxy
        self._entity_type = entity_type

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self.proxy.device_info

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return slugify(f"{self.proxy.vin}-{self._entity_type}")

    @property
    def name(self):
        """Return the name of this entity."""
        return f"{self.proxy.vin}-{self._entity_type}"


class RenaultBatteryDataEntity(RenaultDataEntity):
    """Implementation of a Renault entity with battery coordinator."""

    def __init__(self, proxy: PyZEVehicleProxy, entity_type: str):
        """Initialise entity."""
        super().__init__(proxy, entity_type, "battery")

    @property
    def device_state_attributes(self):
        """Return the state attributes of this entity."""
        attrs = {}
        data = self.coordinator.data
        if "timestamp" in data:
            attrs[ATTR_LAST_UPDATE] = data["timestamp"]
        return attrs
