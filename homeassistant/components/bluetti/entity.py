"""Base entity for the BLUETTI integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BluettiDeviceCoordinator
from .models import BluettiDevice, BluettiState


class BluettiEntity(CoordinatorEntity[BluettiDeviceCoordinator]):
    """Common behavior shared by all BLUETTI entities."""

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
