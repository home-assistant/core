"""SFR Box sensor platform."""
from collections.abc import Callable
from dataclasses import dataclass

from sfrbox_api.models import DslInfo, SystemInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData


@dataclass
class SFRBoxSensorMixin:
    """Mixin for SFR Box sensors."""

    value_fn: Callable[[DslInfo], StateType]


@dataclass
class SFRBoxSensorEntityDescription(SensorEntityDescription, SFRBoxSensorMixin):
    """Description for SFR Box sensors."""


SENSOR_TYPES: tuple[SFRBoxSensorEntityDescription, ...] = (
    SFRBoxSensorEntityDescription(
        key="linemode",
        name="Line mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.linemode,
    ),
    SFRBoxSensorEntityDescription(
        key="counter",
        name="Counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.counter,
    ),
    SFRBoxSensorEntityDescription(
        key="crc",
        name="CRC",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.crc,
    ),
    SFRBoxSensorEntityDescription(
        key="noise_down",
        name="Noise down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.noise_down,
    ),
    SFRBoxSensorEntityDescription(
        key="noise_up",
        name="Noise up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.noise_up,
    ),
    SFRBoxSensorEntityDescription(
        key="attenuation_down",
        name="Attenuation down",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.attenuation_down,
    ),
    SFRBoxSensorEntityDescription(
        key="attenuation_up",
        name="Attenuation up",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.attenuation_up,
    ),
    SFRBoxSensorEntityDescription(
        key="rate_down",
        name="Rate down",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.rate_down,
    ),
    SFRBoxSensorEntityDescription(
        key="rate_up",
        name="Rate up",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.rate_up,
    ),
    SFRBoxSensorEntityDescription(
        key="line_status",
        name="Line status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "No Defect",
            "Of Frame",
            "Loss Of Signal",
            "Loss Of Power",
            "Loss Of Signal Quality",
            "Unknown",
        ],
        value_fn=lambda x: x.line_status,
    ),
    SFRBoxSensorEntityDescription(
        key="training",
        name="Training",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        options=[
            "Idle",
            "G.994 Training",
            "G.992 Started",
            "G.922 Channel Analysis",
            "G.992 Message Exchange",
            "G.993 Started",
            "G.993 Channel Analysis",
            "G.993 Message Exchange",
            "Showtime",
            "Unknown",
        ],
        value_fn=lambda x: x.training,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SFRBoxSensor(data.dsl, description, data.system.data)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


class SFRBoxSensor(CoordinatorEntity[SFRDataUpdateCoordinator[DslInfo]], SensorEntity):
    """SFR Box sensor."""

    entity_description: SFRBoxSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[DslInfo],
        description: SFRBoxSensorEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{system_info.mac_addr}_dsl_{description.key}"
        self._attr_device_info = {"identifiers": {(DOMAIN, system_info.mac_addr)}}

    @property
    def native_value(self) -> StateType:
        """Return the native value of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
