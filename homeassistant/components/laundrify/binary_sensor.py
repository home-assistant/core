"""Platform for binary sensor integration."""

from __future__ import annotations

import logging

from laundrify_aio import LaundrifyDevice

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODELS
from .coordinator import LaundrifyUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry created in the integrations UI."""

    coordinator: LaundrifyUpdateCoordinator = hass.data[DOMAIN][config.entry_id][
        "coordinator"
    ]

    async_add_entities(
        LaundrifyPowerPlug(coordinator, device) for device in coordinator.data.values()
    )


class LaundrifyPowerPlug(
    CoordinatorEntity[LaundrifyUpdateCoordinator], BinarySensorEntity
):
    """Representation of a laundrify Power Plug."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_unique_id: str
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "wash_cycle"

    def __init__(
        self, coordinator: LaundrifyUpdateCoordinator, device: LaundrifyDevice
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._device = device
        unique_id = device.id
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=MODELS[device.model],
            sw_version=device.firmwareVersion,
            configuration_url=f"http://{device.internalIP}",
        )

    @property
    def available(self) -> bool:
        """Check if the device is available."""
        return (
            self._attr_unique_id in self.coordinator.data
            and self.coordinator.last_update_success
        )

    @property
    def is_on(self) -> bool:
        """Return entity state."""
        return bool(self._device.status == "ON")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._device = self.coordinator.data[self._attr_unique_id]
        super()._handle_coordinator_update()
