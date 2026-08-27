"""Base entities for the BLUETTI integration's cloud and optional local Modbus sources."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BluettiDeviceCoordinator, BluettiModbusCoordinator
from .models import BluettiDevice, BluettiState


class BluettiEntity(CoordinatorEntity[BluettiDeviceCoordinator]):
    """Common behavior shared by all BLUETTI entities.

    Subclasses are expected to set self._attr_name after calling super().__init__(),
    since the name source (a device state's fn_name, or a static label) varies by
    platform.
    """

    _attr_has_entity_name = True

    def __init__(self, device: BluettiDevice, state: BluettiState) -> None:
        """Initialize the entity from its owning device and cloud state."""
        assert device.coordinator is not None, (
            "entities must be created after the device's coordinator is wired up"
        )
        super().__init__(device.coordinator)
        self._device = device
        self._state_obj = state

        self._attr_unique_id = f"{device.device_id}_{state.fn_code}"
        # fn_code doubles as the icon translation key (see icons.json); it's
        # a stable, bounded identifier already used for unique_id above.
        # Lowercased because translation keys must match hassfest's
        # [a-z0-9-_]+ pattern, but the cloud's fn_code values are mixed-case
        # (e.g. "SOC", "SetCtrlAc") - icons.json's keys are lowercased to
        # match.
        self._attr_translation_key = state.fn_code.lower()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.sn,
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the entity should be considered available."""
        if not super().available:
            return False
        # The power switch itself should stay controllable even if the
        # device otherwise reports as offline.
        if self._state_obj.fn_code == "SetCtrlPowerOn":
            return True
        return self._device.online


class BluettiModbusEntity(CoordinatorEntity[BluettiModbusCoordinator]):
    """Common behavior shared by BLUETTI entities sourced from local Modbus.

    Uses the same device identifier as BluettiEntity so Modbus-sourced
    entities group under the same Home Assistant device as their
    cloud-sourced siblings, rather than appearing as a separate device.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        device: BluettiDevice,
        coordinator: BluettiModbusCoordinator,
        field_name: str,
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
    @override
    def available(self) -> bool:
        """Return whether the coordinator's last poll included this field."""
        if not super().available:
            return False
        return self._field_name in (self.coordinator.data or {})
