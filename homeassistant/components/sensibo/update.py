"""Update platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysensibo.model import SensiboDevice

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_version: Callable[[SensiboDevice], str | None]
    value_available: Callable[[SensiboDevice], str | None]


@dataclass
class SensiboDeviceUpdateEntityDescription(
    UpdateEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Sensibo Update entity."""


DEVICE_SENSOR_TYPES: tuple[SensiboDeviceUpdateEntityDescription, ...] = (
    SensiboDeviceUpdateEntityDescription(
        key="fw_ver_available",
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        name="Update available",
        icon="mdi:rocket-launch",
        value_version=lambda data: data.fw_ver,
        value_available=lambda data: data.fw_ver_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo Update platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboDeviceUpdate(coordinator, device_id, description)
        for description in DEVICE_SENSOR_TYPES
        for device_id, device_data in coordinator.data.parsed.items()
        if description.value_available(device_data) is not None
    )


class SensiboDeviceUpdate(SensiboDeviceBaseEntity, UpdateEntity):
    """Representation of a Sensibo Device Update."""

    entity_description: SensiboDeviceUpdateEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboDeviceUpdateEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Update."""
        super().__init__(coordinator, device_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"
        self._attr_title = self.device_data.model

    @property
    def installed_version(self) -> str | None:
        """Return version currently installed."""
        return self.entity_description.value_version(self.device_data)

    @property
    def latest_version(self) -> str | None:
        """Return latest available version."""
        return self.entity_description.value_available(self.device_data)
