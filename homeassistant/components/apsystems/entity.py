"""APsystems base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ApSystemsData, Lake6Coordinator


class ApSystemsEntity(Entity):
    """Defines a base APsystems entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the APsystems entity."""

        # Handle device version safely
        sw_version = None
        if data.coordinator.device_version:
            version_parts = data.coordinator.device_version.split(" ")
            if len(version_parts) > 1:
                sw_version = version_parts[1]
            else:
                sw_version = version_parts[0]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.device_id)},
            manufacturer="APsystems",
            model="EZ1-M",
            serial_number=data.device_id,
            sw_version=sw_version,
        )


class Lake6Entity(CoordinatorEntity[Lake6Coordinator]):
    """Base entity shared by every Lake_6 platform.

    Only the device identity is shared here; each platform supplies its own
    entity description and unique id.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: Lake6Coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.dev_id)},
            manufacturer="APsystems",
            # type comes from /devices and is shown as reported, with no mapping.
            model=device.device_type,
            serial_number=device.dev_id,
            # The client layer already turned an empty firmware version into
            # None, which hides the firmware row on the device page.
            sw_version=device.sw_version,
        )

    @property
    def device_id(self) -> str:
        """Return the device id used to build entity unique ids."""
        return self.coordinator.device.dev_id
