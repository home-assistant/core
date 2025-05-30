"""APsystems base entity."""

from __future__ import annotations

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
