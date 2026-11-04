"""Base entities for the Zendure integration."""

from zendure import PropertyValue
from zendure.catalog import lookup_device

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import ZendureDataUpdateCoordinator


class ZendureEntity(CoordinatorEntity[ZendureDataUpdateCoordinator]):
    """An entity of a Zendure device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZendureDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        snapshot = coordinator.data
        self._attr_unique_id = f"{snapshot.serial_number}_{description.key}"
        # The library only produces snapshots for registered models.
        model = lookup_device(snapshot.product_raw).display_name
        self._attr_device_info = DeviceInfo(
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            identifiers={(DOMAIN, snapshot.serial_number)},
            manufacturer=MANUFACTURER,
            model=model,
            model_id=snapshot.product_raw,
            name=model,
            serial_number=snapshot.serial_number,
        )

    @property
    def raw_value(self) -> PropertyValue:
        """Return the reported value for this entity's key."""
        return self.coordinator.data.properties.get(self.entity_description.key)
