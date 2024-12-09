"""Sensors for AIS tracker."""

from collections.abc import Callable
from dataclasses import dataclass

from pyais.constants import ManeuverIndicator, NavigationStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import DEGREE, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MMSIS, DOMAIN
from .coordinator import AisTrackerConfigEntry, AisTrackerCoordinator
from .entity import AistrackerEntity


@dataclass(frozen=True, kw_only=True)
class AisSensorEntityDescription(SensorEntityDescription):
    """A class that describes AEMET OpenData sensor entities."""

    keys: list[str] | None = None
    value_fn: Callable[[str | float], float | int | str | None] = lambda value: value


def _course_value(value: str | float) -> float | None:
    if float(value) == 360:
        return None
    return float(value)


def _heading_value(value: str | float) -> int | None:
    if int(value) == 511:
        return None
    return int(value)


def _turn_value(value: str | float) -> float | None:
    if float(value) == -128.0:
        return None
    return (float(value) / 4.733) ** 2


SENSORS: tuple[AisSensorEntityDescription, ...] = (
    AisSensorEntityDescription(
        key="course",
        translation_key="course",
        native_unit_of_measurement=DEGREE,
        value_fn=_course_value,
    ),
    AisSensorEntityDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement=DEGREE,
        value_fn=_heading_value,
    ),
    AisSensorEntityDescription(
        key="maneuver",
        translation_key="maneuver",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name for status in ManeuverIndicator],
        value_fn=lambda value: ManeuverIndicator(int(value)).name,
    ),
    AisSensorEntityDescription(
        key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        value_fn=lambda value: float(value) / 10,
    ),
    AisSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name for status in NavigationStatus],
        value_fn=lambda value: NavigationStatus(int(value)).name,
    ),
    AisSensorEntityDescription(
        key="turn",
        translation_key="turn",
        native_unit_of_measurement="°/min",
        value_fn=_turn_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AisTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for AIS tracker."""
    coordinator = entry.runtime_data

    async_add_entities(
        AisTrackerSensorEntity(coordinator, mmsi, description)
        for mmsi in entry.data[CONF_MMSIS]
        for description in SENSORS
    )


class AisTrackerSensorEntity(AistrackerEntity, SensorEntity):
    """Represent a tracked device."""

    entity_description: AisSensorEntityDescription

    def __init__(
        self,
        coordinator: AisTrackerCoordinator,
        mmsi: str,
        description: AisSensorEntityDescription,
    ) -> None:
        """Set up AIS tracker tracker entity."""
        super().__init__(coordinator, mmsi)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{mmsi}_{description.key}"

    @property
    def native_value(self) -> float | int | str | None:
        """Return the state of the device."""
        if (data := self.data) is not None and (
            value := data.get(self.entity_description.key)
        ) is not None:
            return self.entity_description.value_fn(value)
        return None
