"""Sensors for AIS tracker."""

from collections.abc import Callable
from dataclasses import dataclass

from pyais.constants import ManeuverIndicator, NavigationStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfSpeed
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MMSIS, DOMAIN


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
        name="course",
        native_unit_of_measurement=DEGREE,
        value_fn=_course_value,
    ),
    AisSensorEntityDescription(
        key="heading",
        name="heading",
        native_unit_of_measurement=DEGREE,
        value_fn=_heading_value,
    ),
    AisSensorEntityDescription(
        key="maneuver",
        name="maneuver",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name for status in ManeuverIndicator],
        value_fn=lambda value: ManeuverIndicator(int(value)).name,
    ),
    AisSensorEntityDescription(
        key="speed",
        name="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        value_fn=lambda value: float(value) / 10,
    ),
    AisSensorEntityDescription(
        key="status",
        name="status",
        device_class=SensorDeviceClass.ENUM,
        options=[status.name for status in NavigationStatus],
        value_fn=lambda value: NavigationStatus(int(value)).name,
    ),
    AisSensorEntityDescription(
        key="turn",
        name="turn",
        native_unit_of_measurement="°/min",
        value_fn=_turn_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for AIS tracker."""

    async_add_entities(
        AisTrackerSensorEntity(mmsi, description)
        for mmsi in entry.data[CONF_MMSIS]
        for description in SENSORS
    )


class AisTrackerSensorEntity(SensorEntity):
    """Represent a tracked device."""

    _attr_should_poll = False
    entity_description: AisSensorEntityDescription

    def __init__(self, mmsi: str, description: AisSensorEntityDescription) -> None:
        """Set up AIS tracker tracker entity."""
        self.entity_description = description
        self._mmsi = mmsi
        self._attr_unique_id = f"ais_mmsi_{mmsi}_{description.key}"
        self._attr_name = f"{mmsi} {description.key}"
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mmsi)}, name=mmsi, serial_number=mmsi
        )

    async def async_update_data_from_msg(self, event: Event) -> None:
        """Update data from received message."""
        msg = event.data
        if (
            msg.get("msg_type") in [1, 2, 3]  # position reports
            and (value := msg.get(self.entity_description.key)) is not None
        ):
            self._attr_native_value = self.entity_description.value_fn(value)
        elif msg.get("msg_type") == 5:  # Static and voyage related data
            self._attr_extra_state_attributes["shipname"] = msg.get("shipname")
            self._attr_extra_state_attributes["callsign"] = msg.get("callsign")

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for updates."""
        self.async_on_remove(
            self.hass.bus.async_listen(
                f"{DOMAIN}_{self._mmsi}", self.async_update_data_from_msg
            )
        )
