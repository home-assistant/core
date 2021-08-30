"""IoTaWatt parent entity class."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_ICON
from .coordinator import IotawattUpdater


class IotaWattEntity(CoordinatorEntity):
    """Defines the base IoTaWatt Energy Device entity."""

    def __init__(self, coordinator: IotawattUpdater, entity, mac_address, name):
        """Initialize the IoTaWatt Entity."""
        super().__init__(coordinator)

        self._entity = entity
        self._attr_name = name
        self._attr_icon = DEFAULT_ICON
        self._attr_unique_id = mac_address
