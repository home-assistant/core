"""Entity classes for the QNAP QSW integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aioqsw.const import (
    QSD_FIRMWARE,
    QSD_FIRMWARE_INFO,
    QSD_MAC,
    QSD_PRODUCT,
    QSD_SYSTEM_BOARD,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MANUFACTURER
from .coordinator import QswUpdateCoordinator


class QswEntity(CoordinatorEntity[QswUpdateCoordinator]):
    """Define an QNAP QSW entity."""

    def __init__(
        self,
        coordinator: QswUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.product = self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT)
        self._attr_device_info = DeviceInfo(
            configuration_url=entry.data[CONF_URL],
            connections={
                (
                    CONNECTION_NETWORK_MAC,
                    self.get_device_value(QSD_SYSTEM_BOARD, QSD_MAC),
                )
            },
            manufacturer=MANUFACTURER,
            model=self.product,
            name=self.product,
            sw_version=self.get_device_value(QSD_FIRMWARE_INFO, QSD_FIRMWARE),
        )

    def get_device_value(self, key: str, subkey: str) -> Any:
        """Return device value by key."""
        value = None
        if key in self.coordinator.data:
            data = self.coordinator.data[key]
            if subkey in data:
                value = data[subkey]
        return value


@dataclass
class QswEntityDescriptionMixin:
    """Mixin to describe a QSW entity."""

    subkey: str


class QswEntityDescription(EntityDescription, QswEntityDescriptionMixin):
    """Class to describe a QSW entity."""

    attributes: dict[str, list[str]] | None = None


class QswSensorEntity(QswEntity):
    """Base class for QSW sensor entities."""

    entity_description: QswEntityDescription

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Update attributes."""
        if self.entity_description.attributes:
            self._attr_extra_state_attributes = {
                key: self.get_device_value(val[0], val[1])
                for key, val in self.entity_description.attributes.items()
            }
