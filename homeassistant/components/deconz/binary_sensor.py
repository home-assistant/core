"""Support for deCONZ binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
from pydeconz.models.sensor import SensorBase as PydeconzSensorBase
from pydeconz.models.sensor.alarm import Alarm
from pydeconz.models.sensor.carbon_monoxide import CarbonMonoxide
from pydeconz.models.sensor.fire import Fire
from pydeconz.models.sensor.generic_flag import GenericFlag
from pydeconz.models.sensor.open_close import OpenClose
from pydeconz.models.sensor.presence import Presence
from pydeconz.models.sensor.vibration import Vibration
from pydeconz.models.sensor.water import Water

from homeassistant.components.binary_sensor import (
    DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_DARK, ATTR_ON
from .deconz_device import DeconzDevice
from .hub import DeconzHub

ATTR_ORIENTATION = "orientation"
ATTR_TILTANGLE = "tiltangle"
ATTR_VIBRATIONSTRENGTH = "vibrationstrength"

PROVIDES_EXTRA_ATTRIBUTES = (
    "alarm",
    "carbon_monoxide",
    "fire",
    "flag",
    "open",
    "presence",
    "vibration",
    "water",
)

T = TypeVar(
    "T",
    Alarm,
    CarbonMonoxide,
    Fire,
    GenericFlag,
    OpenClose,
    Presence,
    Vibration,
    Water,
    PydeconzSensorBase,
)


@dataclass(frozen=True, kw_only=True)
class DeconzBinarySensorDescription(Generic[T], BinarySensorEntityDescription):
    """Class describing deCONZ binary sensor entities."""

    instance_check: type[T] | None = None
    name_suffix: str = ""
    old_unique_id_suffix: str = ""
    update_key: str
    value_fn: Callable[[T], bool | None]


ENTITY_DESCRIPTIONS: tuple[DeconzBinarySensorDescription, ...] = (
    DeconzBinarySensorDescription[Alarm](
        key="alarm",
        update_key="alarm",
        value_fn=lambda device: device.alarm,
        instance_check=Alarm,
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    DeconzBinarySensorDescription[CarbonMonoxide](
        key="carbon_monoxide",
        update_key="carbonmonoxide",
        value_fn=lambda device: device.carbon_monoxide,
        instance_check=CarbonMonoxide,
        device_class=BinarySensorDeviceClass.CO,
    ),
    DeconzBinarySensorDescription[Fire](
        key="fire",
        update_key="fire",
        value_fn=lambda device: device.fire,
        instance_check=Fire,
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    DeconzBinarySensorDescription[Fire](
        key="in_test_mode",
        update_key="test",
        value_fn=lambda device: device.in_test_mode,
        instance_check=Fire,
        name_suffix="Test Mode",
        old_unique_id_suffix="test mode",
        device_class=BinarySensorDeviceClass.SMOKE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzBinarySensorDescription[GenericFlag](
        key="flag",
        update_key="flag",
        value_fn=lambda device: device.flag,
        instance_check=GenericFlag,
    ),
    DeconzBinarySensorDescription[OpenClose](
        key="open",
        update_key="open",
        value_fn=lambda device: device.open,
        instance_check=OpenClose,
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    DeconzBinarySensorDescription[Presence](
        key="presence",
        update_key="presence",
        value_fn=lambda device: device.presence,
        instance_check=Presence,
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    DeconzBinarySensorDescription[Vibration](
        key="vibration",
        update_key="vibration",
        value_fn=lambda device: device.vibration,
        instance_check=Vibration,
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    DeconzBinarySensorDescription[Water](
        key="water",
        update_key="water",
        value_fn=lambda device: device.water,
        instance_check=Water,
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    DeconzBinarySensorDescription[SensorResources](
        key="tampered",
        update_key="tampered",
        value_fn=lambda device: device.tampered,
        name_suffix="Tampered",
        old_unique_id_suffix="tampered",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzBinarySensorDescription[SensorResources](
        key="low_battery",
        update_key="lowbattery",
        value_fn=lambda device: device.low_battery,
        name_suffix="Low Battery",
        old_unique_id_suffix="low battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ binary sensor."""
    hub = DeconzHub.get_hub(hass, config_entry)
    hub.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = hub.api.sensors[sensor_id]

        for description in ENTITY_DESCRIPTIONS:
            if (
                description.instance_check
                and not isinstance(sensor, description.instance_check)
            ) or description.value_fn(sensor) is None:
                continue
            async_add_entities([DeconzBinarySensor(sensor, hub, description)])

    hub.register_platform_add_device_callback(
        async_add_sensor,
        hub.api.sensors,
    )


class DeconzBinarySensor(DeconzDevice[SensorResources], BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    TYPE = DOMAIN
    entity_description: DeconzBinarySensorDescription

    def __init__(
        self,
        device: SensorResources,
        hub: DeconzHub,
        description: DeconzBinarySensorDescription,
    ) -> None:
        """Initialize deCONZ binary sensor."""
        self.entity_description = description
        self.unique_id_suffix = description.key
        self._update_key = description.update_key
        if description.name_suffix:
            self._name_suffix = description.name_suffix
        super().__init__(device, hub)

        if (
            self.entity_description.key in PROVIDES_EXTRA_ATTRIBUTES
            and self._update_keys is not None
        ):
            self._update_keys.update({"on", "state"})

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | list | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | list | None] = {}

        if self.entity_description.key not in PROVIDES_EXTRA_ATTRIBUTES:
            return attr

        if self._device.on is not None:
            attr[ATTR_ON] = self._device.on

        if self._device.internal_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.internal_temperature

        if isinstance(self._device, Presence):
            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

        elif isinstance(self._device, Vibration):
            attr[ATTR_ORIENTATION] = self._device.orientation
            attr[ATTR_TILTANGLE] = self._device.tilt_angle
            attr[ATTR_VIBRATIONSTRENGTH] = self._device.vibration_strength

        return attr
