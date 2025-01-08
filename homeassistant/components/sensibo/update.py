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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SensiboConfigEntry
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SensiboDeviceUpdateEntityDescription(UpdateEntityDescription):
    """Describes Sensibo Update entity."""

    value_version: Callable[[SensiboDevice], str | None]
    value_available: Callable[[SensiboDevice], str | None]


DEVICE_SENSOR_TYPES: tuple[SensiboDeviceUpdateEntityDescription, ...] = (
    SensiboDeviceUpdateEntityDescription(
        key="fw_ver_available",
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_version=lambda data: data.fw_ver,
        value_available=lambda data: data.fw_ver_available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensiboConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensibo Update platform."""

    coordinator = entry.runtime_data

    added_devices: set[str] = set()

    def _add_remove_devices() -> None:
        """Handle additions of devices and sensors."""
        nonlocal added_devices
        new_devices, _, added_devices = coordinator.get_devices(added_devices)

        if new_devices:
            async_add_entities(
                SensiboDeviceUpdate(coordinator, device_id, description)
                for device_id, device_data in coordinator.data.parsed.items()
                if device_id in new_devices
                for description in DEVICE_SENSOR_TYPES
                if description.value_available(device_data) is not None
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_remove_devices))
    _add_remove_devices()


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
