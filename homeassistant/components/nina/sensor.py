"""NINA sensor platform."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MESSAGE_SLOTS, CONF_REGIONS, SEVERITY_VALUES
from .coordinator import NinaConfigEntry, NINADataUpdateCoordinator
from .entity import NinaEntity

PARALLEL_UPDATES = 0


# pylint: disable=fixme
class SensorDataPoints(StrEnum):
    """Enum of data point."""

    HEADLINE = "headline"
    SENDER = "sender"
    SEVERITY = "severity"  # TODO set possible options in entity
    AFFECTED_AREAS = "affected_areas"
    MORE_INFORMATION_URL = "more_info_url"


@dataclass
class SensorData:
    """Representation of a sensor configuration."""

    type: SensorDataPoints
    friendly_name: str
    entity_description: SensorEntityDescription | None


FRIENDLY_NAME_MAPPING = {
    SensorDataPoints.HEADLINE: "Headline",
    SensorDataPoints.SENDER: "Sender",
    SensorDataPoints.SEVERITY: "Severity",
    SensorDataPoints.AFFECTED_AREAS: "Affected Areas",
    SensorDataPoints.MORE_INFORMATION_URL: "More Information",
}

ENTITY_DESCRIPTION_MAPPING = {
    SensorDataPoints.HEADLINE: SensorEntityDescription(
        key="headline",
        icon="mdi:text-short",
    ),
    SensorDataPoints.SENDER: SensorEntityDescription(
        key="sender",
        icon="mdi:account-tie-voice",
    ),
    SensorDataPoints.SEVERITY: SensorEntityDescription(
        key="severity",
        options=SEVERITY_VALUES,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:alert",
    ),
    SensorDataPoints.AFFECTED_AREAS: SensorEntityDescription(
        key="affected_areas",
        icon="mdi:map-marker-radius",
    ),
    SensorDataPoints.MORE_INFORMATION_URL: SensorEntityDescription(
        key="more_info_url",
        icon="mdi:web",
    ),
}


def create_sensors_for_warning(
    coordinator: NINADataUpdateCoordinator, region: str, region_name: str, slot_id: int
) -> Sequence["NinaSensor"]:
    """Create sensors for a warning."""
    return [
        NinaSensor(
            coordinator,
            region,
            region_name,
            slot_id,
            SensorData(
                sensor_type,
                FRIENDLY_NAME_MAPPING.get(sensor_type, sensor_type.value),
                ENTITY_DESCRIPTION_MAPPING.get(sensor_type),
            ),
        )
        for sensor_type in SensorDataPoints
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NinaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NINA sensor platform."""

    coordinator = config_entry.runtime_data

    regions: dict[str, str] = config_entry.data[CONF_REGIONS]
    message_slots: int = config_entry.data[CONF_MESSAGE_SLOTS]

    entities = [
        create_sensors_for_warning(coordinator, ent, regions[ent], i + 1)
        for ent in coordinator.data
        for i in range(message_slots)
    ]

    async_add_entities(
        [entity for slot_entities in entities for entity in slot_entities]
    )


class NinaSensor(NinaEntity, SensorEntity):
    """Representation of a NINA headline."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NINADataUpdateCoordinator,
        region: str,
        region_name: str,
        slot_id: int,
        sensor_data: SensorData,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, region, slot_id)

        self._sensor_data: SensorData = sensor_data

        self._attr_name = f"{sensor_data.friendly_name}: {region_name} {slot_id}"
        self._attr_unique_id = f"{region_name}_{slot_id}-{sensor_data.type.value}"
        self._attr_device_info = coordinator.device_info

        if sensor_data.entity_description:
            self.entity_description = sensor_data.entity_description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._active_warning_count > self._warning_index

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return getattr(self._get_warning_data(), self._sensor_data.type.value, None)
