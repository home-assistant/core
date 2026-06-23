"""Sensor platform for Grandstream integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GrandstreamConfigEntry
from .coordinator import GrandstreamCoordinator

_LOGGER = logging.getLogger(__name__)


def _map_phone_status(value: str) -> str | None:
    """Map phone status values."""
    if isinstance(value, str):
        value = value.strip()
    if value == "unavailable":
        return "no_available_account"
    if value == "unknown":
        return None
    return value


@dataclass(frozen=True, kw_only=True)
class GrandstreamSensorEntityDescription(SensorEntityDescription):
    """Describes Grandstream sensor entity."""

    value_fn: Callable[[str], str | None]


# Device status sensors
DEVICE_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="phone_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "no_available_account",
            "busy",
            "preview",
            "ringing",
            "offline",
        ],
        icon="mdi:account-badge",
        value_fn=_map_phone_status,
    ),
)


async def async_setup_entry(
    _: HomeAssistant,
    config_entry: GrandstreamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    runtime_data = config_entry.runtime_data
    coordinator = runtime_data.coordinator
    device_info = runtime_data.device_info

    entities = [
        GrandstreamDeviceSensor(coordinator, device_info, description)
        for description in DEVICE_SENSORS
    ]

    async_add_entities(entities)


class GrandstreamDeviceSensor(CoordinatorEntity[GrandstreamCoordinator], SensorEntity):
    """Representation of a Grandstream device sensor."""

    entity_description: GrandstreamSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GrandstreamCoordinator,
        device_info: DeviceInfo,
        description: GrandstreamSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
