"""Base entity module for Daikin smart AC."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DaikinDataUpdateCoordinator


# pylint: disable=too-few-public-methods
class DaikinEntity(CoordinatorEntity[DaikinDataUpdateCoordinator]):
    """Base entity for Daikin devices using a DataUpdateCoordinator."""

    _attr_has_entity_name = True

    if TYPE_CHECKING:
        _unique_id: str
        _device_name: str
        _device_info: dict[str, Any]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        unique_id = getattr(self, "_unique_id", None)
        device_name = getattr(self, "_device_name", None)
        device_info = getattr(self, "_device_info", None)
        if unique_id is None or device_name is None or device_info is None:
            raise AttributeError("Entity attributes not set yet")
        return DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
            manufacturer="Daikin",
            model="Smart AC Series",
            sw_version=device_info.get("fw_ver"),
        )
