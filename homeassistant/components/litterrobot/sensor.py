"""Support for Litter-Robot sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Union, cast

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, Robot

from homeassistant.components.sensor import (
    DOMAIN as PLATFORM,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MASS_POUNDS, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT, async_update_unique_id
from .hub import LitterRobotHub


def icon_for_gauge_level(gauge_level: int | None = None, offset: int = 0) -> str:
    """Return a gauge icon valid identifier."""
    if gauge_level is None or gauge_level <= 0 + offset:
        return "mdi:gauge-empty"
    if gauge_level > 70 + offset:
        return "mdi:gauge-full"
    if gauge_level > 30 + offset:
        return "mdi:gauge"
    return "mdi:gauge-low"


@dataclass
class RobotSensorEntityDescription(SensorEntityDescription, Generic[_RobotT]):
    """A class that describes robot sensor entities."""

    icon_fn: Callable[[Any], str | None] = lambda _: None
    should_report: Callable[[_RobotT], bool] = lambda _: True


class LitterRobotSensorEntity(LitterRobotEntity[_RobotT], SensorEntity):
    """Litter-Robot sensor entity."""

    entity_description: RobotSensorEntityDescription[_RobotT]

    @property
    def native_value(self) -> float | datetime | str | None:
        """Return the state."""
        if self.entity_description.should_report(self.robot):
            if isinstance(val := getattr(self.robot, self.entity_description.key), str):
                return val.lower()
            return cast(Union[float, datetime, None], val)
        return None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if (icon := self.entity_description.icon_fn(self.state)) is not None:
            return icon
        return super().icon


ROBOT_SENSOR_MAP: dict[type[Robot], list[RobotSensorEntityDescription]] = {
    LitterRobot: [
        RobotSensorEntityDescription[LitterRobot](
            key="waste_drawer_level",
            name="Waste Drawer",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_start_time",
            name="Sleep Mode Start Time",
            device_class=SensorDeviceClass.TIMESTAMP,
            should_report=lambda robot: robot.sleep_mode_enabled,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="sleep_mode_end_time",
            name="Sleep Mode End Time",
            device_class=SensorDeviceClass.TIMESTAMP,
            should_report=lambda robot: robot.sleep_mode_enabled,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="last_seen",
            name="Last Seen",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        RobotSensorEntityDescription[LitterRobot](
            key="status_code",
            name="Status Code",
            device_class="litterrobot__status_code",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ],
    LitterRobot4: [
        RobotSensorEntityDescription[LitterRobot4](
            key="pet_weight",
            name="Pet weight",
            icon="mdi:scale",
            native_unit_of_measurement=MASS_POUNDS,
        )
    ],
    FeederRobot: [
        RobotSensorEntityDescription[FeederRobot](
            key="food_level",
            name="Food level",
            native_unit_of_measurement=PERCENTAGE,
            icon_fn=lambda state: icon_for_gauge_level(state, 10),
        )
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    entities = [
        LitterRobotSensorEntity(robot=robot, hub=hub, description=description)
        for robot in hub.account.robots
        for robot_type, entity_descriptions in ROBOT_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    ]
    async_update_unique_id(hass, PLATFORM, entities)
    async_add_entities(entities)
