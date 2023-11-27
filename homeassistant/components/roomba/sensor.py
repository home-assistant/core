"""Sensor platform for Roomba."""
from collections.abc import Callable
from dataclasses import dataclass

from roombapy import Roomba

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .irobot_base import IRobotEntity
from .models import RoombaData


@dataclass
class RoombaSensorEntityDescriptionMixin:
    """Mixin for describing Roomba data."""

    value_fn: Callable[[IRobotEntity], StateType]


@dataclass
class RoombaSensorEntityDescription(
    SensorEntityDescription, RoombaSensorEntityDescriptionMixin
):
    """Immutable class for describing Roomba data."""


SENSORS: list[RoombaSensorEntityDescription] = [
    RoombaSensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.battery_level,
    ),
    RoombaSensorEntityDescription(
        key="battery_cycles",
        translation_key="battery_cycles",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.battery_stats.get("nLithChrg")
        or self.battery_stats.get("nNimhChrg"),
    ),
    RoombaSensorEntityDescription(
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.run_stats.get("hr"),
    ),
    RoombaSensorEntityDescription(
        key="average_mission_time",
        translation_key="average_mission_time",
        icon="mdi:clock",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.mission_stats.get("aMssnM"),
    ),
    RoombaSensorEntityDescription(
        key="total_missions",
        translation_key="total_missions",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Missions",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.mission_stats.get("nMssn"),
    ),
    RoombaSensorEntityDescription(
        key="successful_missions",
        translation_key="successful_missions",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Missions",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.mission_stats.get("nMssnOk"),
    ),
    RoombaSensorEntityDescription(
        key="canceled_missions",
        translation_key="canceled_missions",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Missions",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.mission_stats.get("nMssnC"),
    ),
    RoombaSensorEntityDescription(
        key="failed_missions",
        translation_key="failed_missions",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Missions",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.mission_stats.get("nMssnF"),
    ),
    RoombaSensorEntityDescription(
        key="scrubs_count",
        translation_key="scrubs_count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Scrubs",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda self: self.run_stats.get("nScrubs"),
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iRobot Roomba vacuum cleaner."""
    domain_data: RoombaData = hass.data[DOMAIN][config_entry.entry_id]
    roomba = domain_data.roomba
    blid = domain_data.blid

    async_add_entities(
        RoombaSensor(roomba, blid, entity_description) for entity_description in SENSORS
    )


class RoombaSensor(IRobotEntity, SensorEntity):
    """Roomba sensor."""

    entity_description: RoombaSensorEntityDescription

    def __init__(
        self,
        roomba: Roomba,
        blid: str,
        entity_description: RoombaSensorEntityDescription,
    ) -> None:
        """Initialize Roomba sensor."""
        super().__init__(roomba, blid)
        self.entity_description = entity_description

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.entity_description.key}_{self._blid}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self)
