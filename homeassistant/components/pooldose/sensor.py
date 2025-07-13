"""Sensors for the Seko Pooldose integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from pooldose.request_handler import RequestStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .const import device_info
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PooldoseSensorEntityDescription(SensorEntityDescription):
    """Describe a Pooldose sensor entity."""

    icon: str | None = None
    entity_category: EntityCategory | None = None
    enabled_by_default: bool = True
    value_fn: Callable[[Any], Any] = lambda data: data[0] if data else None


SENSOR_DESCRIPTIONS: tuple[PooldoseSensorEntityDescription, ...] = (
    PooldoseSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        icon="mdi:thermometer",
    ),
    PooldoseSensorEntityDescription(
        key="ph",
        icon="mdi:ph",
    ),
    PooldoseSensorEntityDescription(
        key="orp",
        icon="mdi:water-check",
    ),
    PooldoseSensorEntityDescription(
        key="ph_type_dosing",
        icon="mdi:flask",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_ph_dosing",
        icon="mdi:pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ofa_ph_value",
        icon="mdi:ph",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_type_dosing",
        icon="mdi:flask",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="peristaltic_orp_dosing",
        icon="mdi:pump",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ofa_orp_value",
        icon="mdi:water-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_type",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_offset",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="ph_calibration_slope",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_type",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_offset",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    PooldoseSensorEntityDescription(
        key="orp_calibration_slope",
        icon="mdi:tune",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client
    serialnumber = entry.data["serialnumber"]
    device_info_dict = entry.runtime_data.device_info

    available = client.available_sensors()
    entities: list[SensorEntity] = []

    for description in SENSOR_DESCRIPTIONS:
        if description.key not in available:
            continue
        entities.append(
            PooldoseSensor(
                coordinator,
                client,
                description,
                serialnumber,
                device_info_dict,
            )
        )

    async_add_entities(entities)


class PooldoseSensor(PooldoseEntity, SensorEntity):
    """Sensor entity for the Seko Pooldose API."""

    entity_description: PooldoseSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        client: Any,
        description: PooldoseSensorEntityDescription,
        serialnumber: str,
        device_info_dict: dict[str, Any],
    ) -> None:
        """Initialize a Pooldose sensor entity."""
        super().__init__(
            coordinator,
            client,
            description.key,
            description.key,
            serialnumber,
            device_info(device_info_dict),
            description.enabled_by_default,
        )
        self.entity_description = description
        self._attr_device_class = description.device_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_entity_registry_enabled_default = description.enabled_by_default

    @property
    def native_value(self) -> float | int | str | None:
        """Return the current value of the sensor."""
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        if status != RequestStatus.SUCCESS:
            _LOGGER.warning(
                "Pooldose API returned status %s, entities will be unavailable", status
            )
            return None

        sensor_data = data.get(self._key)
        if not sensor_data:
            return None

        return self.entity_description.value_fn(sensor_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement, determined dynamically from API data."""
        if not self.coordinator.data:
            return None

        status, data = self.coordinator.data
        sensor_data = data.get(self._key)
        if sensor_data and len(sensor_data) > 1:
            unit = sensor_data[1]
            if unit and unit != "UNDEFINED":
                return unit

        return None
