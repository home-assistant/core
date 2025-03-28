"""Entity object for shared properties of Awtrix entities."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AwtrixCoordinator

ENTITY_ID_FORMAT = DOMAIN + ".{}"

class AwtrixEntity(CoordinatorEntity[AwtrixCoordinator]):
    """Generic Awtrix entity (base class)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AwtrixCoordinator, key: str) -> None:
        """Initialize the AWTRIX entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = generate_entity_id(
             ENTITY_ID_FORMAT, self.coordinator.data.uid + "_" + key, hass=self.hass)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.uid)},
            name=self.coordinator.data.uid,
            model="AWTRIX 3",
            sw_version=self.coordinator.data.version,
            manufacturer="Blueforcer",
            configuration_url=f"http://{self.coordinator.data.ip_address}",
            suggested_area="Work Room"
         )
