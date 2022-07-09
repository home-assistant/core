"""Base Entity for JustNimbus sensors."""
from __future__ import annotations

import justnimbus

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.entity import DeviceInfo

from . import JustNimbusCoordinator
from .const import DOMAIN


class JustNimbusEntity(
    update_coordinator.CoordinatorEntity[justnimbus.JustNimbusModel],
    SensorEntity,
):
    """Defines a base JustNimbus entity."""

    def __init__(
        self,
        *,
        client: justnimbus.JustNimbusClient,
        entry_id: str,
        device_id: str,
        coordinator: JustNimbusCoordinator,
    ) -> None:
        """Initialize the JustNimbus entity."""
        super().__init__(coordinator=coordinator)
        self._entry_id = entry_id
        self._device_id = device_id
        self.client = client

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device information about the application."""
        if self._device_id is None:
            return None

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="Just Nimbus Sensor",
            manufacturer="Just Nimbus",
            suggested_area="Basement",
            via_device=(DOMAIN, self._device_id),
        )

    @property
    def available(self) -> bool:
        """Return device availability."""
        return getattr(self.coordinator.data, "error_code") == 0
