"""Sensor platform for Grandstream integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from grandstream_home_api import get_by_path

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

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
        icon="mdi:account-badge",
    ),
)


class GrandstreamSensor(SensorEntity):
    """Base class for Grandstream sensors."""

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
        super().__init__()
        self.coordinator = coordinator
        self._attr_device_info = device_info
        self.entity_description = description
        self._attr_unique_id = f"{unique_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and super().available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )


class GrandstreamDeviceSensor(GrandstreamSensor):
    """Representation of a Grandstream device sensor."""

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        # For phone_status sensor, check connection state first
        if self.entity_description.key == "phone_status":
            # Get API from config entry runtime_data
            config_entry = self.coordinator.config_entry
            if (
                config_entry
                and hasattr(config_entry, "runtime_data")
                and config_entry.runtime_data
            ):
                api = config_entry.runtime_data.api
                # Return connection status key if there's any issue
                if (
                    hasattr(api, "is_ha_control_enabled")
                    and not api.is_ha_control_enabled
                ):
                    return "ha_control_disabled"
                if hasattr(api, "is_online") and not api.is_online:
                    return "offline"
                if hasattr(api, "is_account_locked") and api.is_account_locked:
                    return "account_locked"
                if hasattr(api, "is_authenticated") and not api.is_authenticated:
                    return "auth_failed"

        if self.entity_description.key_path:
            return get_by_path(self.coordinator.data, self.entity_description.key_path)
        return None


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
