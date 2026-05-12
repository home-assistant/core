"""Sensor platform for Grandstream integration."""

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


@dataclass(frozen=True, kw_only=True)
class GrandstreamSensorEntityDescription(SensorEntityDescription):
    """Describes Grandstream sensor entity."""

    key_path: str | None = None


# Device status sensors
DEVICE_SENSORS: tuple[GrandstreamSensorEntityDescription, ...] = (
    GrandstreamSensorEntityDescription(
        key="phone_status",
        key_path="phone_status",
        translation_key="device_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "available",
            "no_available_account",
            "busy",
            "preview",
            "ringing",
            "offline",
            "auth_failed",
            "ha_control_disabled",
            "account_locked",
        ],
        icon="mdi:account-badge",
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
    unique_id = runtime_data.unique_id

    entities = [
        GrandstreamDeviceSensor(coordinator, device_info, unique_id, description)
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
        unique_id: str,
        description: GrandstreamSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        value = self.coordinator.data

        # Strip whitespace from value
        if isinstance(value, str):
            value = value.strip()

        # Map unavailable to no_available_account (unavailable is entity state)
        if value == "unavailable":
            return "no_available_account"

        # Return None for unknown (not in options)
        if value == "unknown":
            return None

        return value
