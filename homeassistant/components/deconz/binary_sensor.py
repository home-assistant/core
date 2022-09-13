"""Support for deCONZ binary sensors."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

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
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import ATTR_DARK, ATTR_ON, DOMAIN as DECONZ_DOMAIN
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

_SensorDeviceT = TypeVar("_SensorDeviceT", bound=PydeconzSensorBase)

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


@callback
def async_update_unique_id(
    hass: HomeAssistant, unique_id: str, entity_class: DeconzBinarySensor
) -> None:
    """Update unique ID to always have a suffix.

    Introduced with release 2022.7.
    """
    ent_reg = er.async_get(hass)

    new_unique_id = f"{unique_id}-{entity_class.unique_id_suffix}"
    if ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, new_unique_id):
        return

    if entity_class.old_unique_id_suffix:
        unique_id = f'{unique_id.split("-", 1)[0]}-{entity_class.old_unique_id_suffix}'

    if entity_id := ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, unique_id):
        ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ binary sensor."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(_: EventType, sensor_id: str) -> None:
        """Add sensor from deCONZ."""
        sensor = gateway.api.sensors[sensor_id]

        for sensor_type, entity_class in ENTITY_CLASSES:
            if TYPE_CHECKING:
                assert isinstance(entity_class, DeconzBinarySensor)
            if (
                not isinstance(sensor, sensor_type)
                or entity_class.unique_id_suffix is not None
                and getattr(sensor, entity_class.unique_id_suffix) is None
            ):
                continue

            async_update_unique_id(hass, sensor.unique_id, entity_class)

            async_add_entities([entity_class(sensor, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors,
    )


class DeconzBinarySensor(DeconzDevice[_SensorDeviceT], BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    old_unique_id_suffix = ""
    TYPE = DOMAIN

    def __init__(self, device: _SensorDeviceT, gateway: DeconzGateway) -> None:
        """Initialize deCONZ binary sensor."""
        super().__init__(device, gateway)

        if (
            self.unique_id_suffix in PROVIDES_EXTRA_ATTRIBUTES
            and self._update_keys is not None
        ):
            self._update_keys.update({"on", "state"})

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | list | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | list | None] = {}

        if self.unique_id_suffix not in PROVIDES_EXTRA_ATTRIBUTES:
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


class DeconzAlarmBinarySensor(DeconzBinarySensor[Alarm]):
    """Representation of a deCONZ alarm binary sensor."""

    unique_id_suffix = "alarm"
    _update_key = "alarm"

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.alarm


class DeconzCarbonMonoxideBinarySensor(DeconzBinarySensor[CarbonMonoxide]):
    """Representation of a deCONZ carbon monoxide binary sensor."""

    unique_id_suffix = "carbon_monoxide"
    _update_key = "carbonmonoxide"

    _attr_device_class = BinarySensorDeviceClass.CO

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.carbon_monoxide


class DeconzFireBinarySensor(DeconzBinarySensor[Fire]):
    """Representation of a deCONZ fire binary sensor."""

    unique_id_suffix = "fire"
    _update_key = "fire"

    _attr_device_class = BinarySensorDeviceClass.SMOKE

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.fire


class DeconzFireInTestModeBinarySensor(DeconzBinarySensor[Fire]):
    """Representation of a deCONZ fire in-test-mode binary sensor."""

    _name_suffix = "Test Mode"
    unique_id_suffix = "in_test_mode"
    old_unique_id_suffix = "test mode"
    _update_key = "test"

    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.in_test_mode


class DeconzFlagBinarySensor(DeconzBinarySensor[GenericFlag]):
    """Representation of a deCONZ generic flag binary sensor."""

    unique_id_suffix = "flag"
    _update_key = "flag"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.flag


class DeconzOpenCloseBinarySensor(DeconzBinarySensor[OpenClose]):
    """Representation of a deCONZ open/close binary sensor."""

    unique_id_suffix = "open"
    _update_key = "open"

    _attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.open


class DeconzPresenceBinarySensor(DeconzBinarySensor[Presence]):
    """Representation of a deCONZ presence binary sensor."""

    unique_id_suffix = "presence"
    _update_key = "presence"

    _attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.presence


class DeconzVibrationBinarySensor(DeconzBinarySensor[Vibration]):
    """Representation of a deCONZ vibration binary sensor."""

    unique_id_suffix = "vibration"
    _update_key = "vibration"

    _attr_device_class = BinarySensorDeviceClass.VIBRATION

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.vibration


class DeconzWaterBinarySensor(DeconzBinarySensor[Water]):
    """Representation of a deCONZ water binary sensor."""

    unique_id_suffix = "water"
    _update_key = "water"

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.water


class DeconzTamperedCommonBinarySensor(DeconzBinarySensor[SensorResources]):
    """Representation of a deCONZ tampered binary sensor."""

    _name_suffix = "Tampered"
    unique_id_suffix = "tampered"
    old_unique_id_suffix = "tampered"
    _update_key = "tampered"

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self._device.tampered


class DeconzLowBatteryCommonBinarySensor(DeconzBinarySensor[SensorResources]):
    """Representation of a deCONZ low battery binary sensor."""

    _name_suffix = "Low Battery"
    unique_id_suffix = "low_battery"
    old_unique_id_suffix = "low battery"
    _update_key = "lowbattery"

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self._device.low_battery


ENTITY_CLASSES = (
    (Alarm, DeconzAlarmBinarySensor),
    (CarbonMonoxide, DeconzCarbonMonoxideBinarySensor),
    (Fire, DeconzFireBinarySensor),
    (Fire, DeconzFireInTestModeBinarySensor),
    (GenericFlag, DeconzFlagBinarySensor),
    (OpenClose, DeconzOpenCloseBinarySensor),
    (Presence, DeconzPresenceBinarySensor),
    (Vibration, DeconzVibrationBinarySensor),
    (Water, DeconzWaterBinarySensor),
    (PydeconzSensorBase, DeconzTamperedCommonBinarySensor),
    (PydeconzSensorBase, DeconzLowBatteryCommonBinarySensor),
)
