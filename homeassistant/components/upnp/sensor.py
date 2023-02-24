"""Support for UPnP/IGD Sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DATA_PACKETS,
    DATA_RATE_PACKETS_PER_SECOND,
    DOMAIN,
    KIBIBYTES_PER_SEC_RECEIVED,
    KIBIBYTES_PER_SEC_SENT,
    LOGGER,
    PACKETS_PER_SEC_RECEIVED,
    PACKETS_PER_SEC_SENT,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    WAN_STATUS,
)
from .coordinator import UpnpDataUpdateCoordinator
from .entity import UpnpEntity, UpnpEntityDescription


@dataclass
class UpnpSensorEntityDescription(UpnpEntityDescription, SensorEntityDescription):
    """A class that describes a sensor UPnP entities."""


SENSOR_DESCRIPTIONS: tuple[UpnpSensorEntityDescription, ...] = (
    UpnpSensorEntityDescription(
        key=BYTES_RECEIVED,
        name=f"{UnitOfInformation.BYTES} received",
        icon="mdi:server-network",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        format="d",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    UpnpSensorEntityDescription(
        key=BYTES_SENT,
        name=f"{UnitOfInformation.BYTES} sent",
        icon="mdi:server-network",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        format="d",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_RECEIVED,
        name=f"{DATA_PACKETS} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_PACKETS,
        format="d",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_SENT,
        name=f"{DATA_PACKETS} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_PACKETS,
        format="d",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    UpnpSensorEntityDescription(
        key=ROUTER_IP,
        name="External IP",
        icon="mdi:server-network",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    UpnpSensorEntityDescription(
        key=ROUTER_UPTIME,
        name="Uptime",
        icon="mdi:server-network",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_registry_enabled_default=False,
        format="d",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    UpnpSensorEntityDescription(
        key=WAN_STATUS,
        name="wan status",
        icon="mdi:server-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    UpnpSensorEntityDescription(
        key=BYTES_RECEIVED,
        value_key=KIBIBYTES_PER_SEC_RECEIVED,
        unique_id="KiB/sec_received",
        name=f"{UnitOfDataRate.KIBIBYTES_PER_SECOND} received",
        icon="mdi:server-network",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        format=".1f",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UpnpSensorEntityDescription(
        key=BYTES_SENT,
        value_key=KIBIBYTES_PER_SEC_SENT,
        unique_id="KiB/sec_sent",
        name=f"{UnitOfDataRate.KIBIBYTES_PER_SECOND} sent",
        icon="mdi:server-network",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KIBIBYTES_PER_SECOND,
        format=".1f",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_RECEIVED,
        value_key=PACKETS_PER_SEC_RECEIVED,
        unique_id="packets/sec_received",
        name=f"{DATA_RATE_PACKETS_PER_SECOND} received",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
        format=".1f",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UpnpSensorEntityDescription(
        key=PACKETS_SENT,
        value_key=PACKETS_PER_SEC_SENT,
        unique_id="packets/sec_sent",
        name=f"{DATA_RATE_PACKETS_PER_SECOND} sent",
        icon="mdi:server-network",
        native_unit_of_measurement=DATA_RATE_PACKETS_PER_SECOND,
        format=".1f",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator: UpnpDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[UpnpSensor] = [
        UpnpSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in SENSOR_DESCRIPTIONS
        if coordinator.data.get(entity_description.key) is not None
    ]

    LOGGER.debug("Adding sensor entities: %s", entities)
    async_add_entities(entities)


class UpnpSensor(UpnpEntity, SensorEntity):
    """Base class for UPnP/IGD sensors."""

    entity_description: UpnpSensorEntityDescription

    @property
    def native_value(self) -> str | None:
        """Return the state of the device."""
        if (key := self.entity_description.value_key) is None:
            return None
        if (value := self.coordinator.data[key]) is None:
            return None
        return format(value, self.entity_description.format)
