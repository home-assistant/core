"""The Tesla Wall Connector integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WallConnectorData
from .const import DOMAIN, WALLCONNECTOR_DEVICE_NAME


@dataclass(frozen=True)
class WallConnectorLambdaValueGetterMixin:
    """Mixin with a function pointer for getting sensor value."""

    value_fn: Callable[[dict], Any]


def _get_unique_id(serial_number: str, key: str) -> str:
    """Get a unique entity name."""
    return f"{serial_number}-{key}"


class WallConnectorEntity(CoordinatorEntity):
    """Base class for Wall Connector entities."""

    _attr_has_entity_name = True

    def __init__(self, wall_connector_data: WallConnectorData) -> None:
        """Initialize WallConnector Entity."""
        self.wall_connector_data = wall_connector_data
        self._attr_unique_id = _get_unique_id(
            wall_connector_data.serial_number, self.entity_description.key
        )
        super().__init__(wall_connector_data.update_coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.wall_connector_data.serial_number)},
            name=WALLCONNECTOR_DEVICE_NAME,
            model=self.wall_connector_data.part_number,
            sw_version=self.wall_connector_data.firmware_version,
            manufacturer="Tesla",
        )
