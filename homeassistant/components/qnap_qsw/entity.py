"""Entity classes for the QNAP QSW integration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aioqsw.const import (
    QSD_FIRMWARE,
    QSD_FIRMWARE_INFO,
    QSD_LACP_PORTS,
    QSD_MAC,
    QSD_PORTS,
    QSD_PRODUCT,
    QSD_SYSTEM_BOARD,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MANUFACTURER
from .coordinator import QswDataCoordinator, QswFirmwareCoordinator


class QswEntityType(StrEnum):
    """QNAP QSW Entity Type."""

    LACP_PORT = QSD_LACP_PORTS
    PORT = QSD_PORTS


class QswDataEntity(CoordinatorEntity[QswDataCoordinator]):
    """Define an QNAP QSW entity."""

    def __init__(
        self,
        coordinator: QswDataCoordinator,
        entry: ConfigEntry,
        type_id: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.type_id = type_id
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

    def get_device_value(
        self,
        key: str,
        subkey: str,
        qsw_type: QswEntityType | None = None,
    ) -> Any:
        """Return device value by key."""
        value = None
        if key in self.coordinator.data:
            data = self.coordinator.data[key]
            if qsw_type is not None and self.type_id is not None:
                if (
                    qsw_type in data
                    and self.type_id in data[qsw_type]
                    and subkey in data[qsw_type][self.type_id]
                ):
                    value = data[qsw_type][self.type_id][subkey]
            elif subkey in data:
                value = data[subkey]
        return value


@dataclass
class QswEntityDescriptionMixin:
    """Mixin to describe a QSW entity."""

    subkey: str


class QswEntityDescription(EntityDescription, QswEntityDescriptionMixin):
    """Class to describe a QSW entity."""

    attributes: dict[str, list[str]] | None = None


class QswSensorEntity(QswDataEntity):
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


class QswFirmwareEntity(CoordinatorEntity[QswFirmwareCoordinator]):
    """Define a QNAP QSW firmware entity."""

    def __init__(
        self,
        coordinator: QswFirmwareCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            configuration_url=entry.data[CONF_URL],
            connections={
                (
                    CONNECTION_NETWORK_MAC,
                    self.get_device_value(QSD_SYSTEM_BOARD, QSD_MAC),
                )
            },
            manufacturer=MANUFACTURER,
            model=self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT),
            name=self.get_device_value(QSD_SYSTEM_BOARD, QSD_PRODUCT),
            sw_version=self.get_device_value(QSD_FIRMWARE_INFO, QSD_FIRMWARE),
        )

    def get_device_value(self, key: str, subkey: str) -> Any:
        """Return device value by key."""
        value = None
        if self.coordinator.data is not None and key in self.coordinator.data:
            data = self.coordinator.data[key]
            if subkey in data:
                value = data[subkey]
        return value
