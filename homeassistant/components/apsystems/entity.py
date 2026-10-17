"""APsystems base entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import ApSystemsData


class ApSystemsEntity(Entity):
    """Defines a base APsystems entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the APsystems entity."""

        # devVer is "<model> <firmware>", e.g. "EZ1-M 1.2.3"; fall back to the
        # EZ1-M default when the firmware string carries no model token.
        model = "EZ1-M"
        sw_version = None
        if data.coordinator.device_version:
            version_parts = data.coordinator.device_version.split(" ")
            if len(version_parts) > 1:
                model = version_parts[0]
                sw_version = version_parts[1]
            else:
                sw_version = version_parts[0]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.device_id)},
            manufacturer="APsystems",
            model=model,
            serial_number=data.device_id,
            sw_version=sw_version,
        )
