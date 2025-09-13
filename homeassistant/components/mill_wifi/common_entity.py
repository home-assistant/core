"""Common base class for Mill WiFi entities."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MillDataCoordinator
from .device_capability import EDeviceCapability
from .device_metric import DeviceMetric

_LOGGER = logging.getLogger(__name__)


class MillEntity(CoordinatorEntity[MillDataCoordinator]):
    """Representation of a Mill WiFi device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillDataCoordinator,
        device_id: str,
        capability: EDeviceCapability | None = None,
    ):
        """Initialize the Mill entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._capability = capability

        device_data = (
            coordinator.data.get(self._device_id) if coordinator.data else None
        )
        device_name = (
            device_data.get("customName", self._device_id)
            if device_data
            else self._device_id
        )
        model_name = (
            DeviceMetric.get_device_type(device_data)
            if device_data
            else "Unknown Mill Device"
        )

        if model_name is None:
            _LOGGER.warning(
                "Model name could not be determined for device %s at init, defaulting to 'Unknown Mill Device'",
                device_id,
            )
            model_name = "Unknown Mill Device"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=str(device_name),
            manufacturer="Mill",
            model=str(model_name),
        )

        if capability:
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{capability.value}"
        else:
            self._attr_unique_id = f"{DOMAIN}_{self._device_id}_entity"

    @property
    def _device(self) -> dict | None:
        """Return the device data from the coordinator."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._device is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._device and self._attr_device_info:
            device_name = self._device.get("customName", self._device_id)
            model_name = DeviceMetric.get_device_type(self._device)

            if self._attr_device_info.get("name") != str(device_name):
                self._attr_device_info["name"] = str(device_name)
            if model_name and self._attr_device_info.get("model") != str(model_name):
                self._attr_device_info["model"] = str(model_name)
            elif (
                not model_name
                and self._attr_device_info.get("model") != "Unknown Mill Device"
            ):
                self._attr_device_info["model"] = "Unknown Mill Device"

        super()._handle_coordinator_update()
