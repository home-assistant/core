"""Base entity for BLUETTI's optional local Modbus data source."""


from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .modbus_coordinator import BluettiModbusCoordinator
from .models import BluettiDevice


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusCoordinator]):
    """Common behavior shared by BLUETTI entities sourced from local Modbus.

    Uses the same device identifier as BluettiEntity so Modbus-sourced
    entities group under the same Home Assistant device as their
    cloud-sourced siblings, rather than appearing as a separate device.
    """

    _attr_has_entity_name = True

    def __init__(
        self, device: BluettiDevice, coordinator: BluettiModbusCoordinator, field_name: str
    ) -> None:
        """Initialize the entity from its owning device and Modbus field name."""
        super().__init__(coordinator)
        self._device = device
        self._field_name = field_name

        self._attr_unique_id = f"{device.device_id}_modbus_{field_name}"
        # Unlike BluettiEntity's fn_code (dynamic, cloud-supplied per
        # device/firmware), bluetti_modbus_lib field names are static and
        # known at development time, so a real translation_key applies here.
        self._attr_translation_key = field_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.sn,
        )

    @property
    def available(self) -> bool:
        """Return whether the coordinator's last poll included this field."""
        if not super().available:
            return False
        return self._field_name in (self.coordinator.data or {})
