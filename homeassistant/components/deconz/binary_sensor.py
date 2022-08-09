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
                or getattr(sensor, entity_class.unique_id_suffix) is None
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

    unique_id_suffix: str
    update_key: str
    value_attr: str

    name_suffix = ""
    old_unique_id_suffix = ""

    TYPE = DOMAIN

    def __init__(self, device: _SensorDeviceT, gateway: DeconzGateway) -> None:
        """Initialize deCONZ binary sensor."""
        super().__init__(device, gateway)

        if self.name_suffix:
            self._attr_name = f"{self._device.name} {self.name_suffix}"

        self._update_keys = {self.update_key, "reachable"}
        if self.unique_id_suffix in PROVIDES_EXTRA_ATTRIBUTES:
            self._update_keys.update({"on", "state"})

        self._attr_is_on = getattr(device, self.value_attr)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{super().unique_id}-{self.unique_id_suffix}"

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        if self._device.changed_keys.intersection(self._update_keys):
            self._attr_is_on = getattr(self._device, self.value_attr)
            super().async_update_callback()

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
    update_key = "alarm"
    value_attr = "alarm"

    _attr_device_class = BinarySensorDeviceClass.SAFETY


class DeconzCarbonMonoxideBinarySensor(DeconzBinarySensor[CarbonMonoxide]):
    """Representation of a deCONZ carbon monoxide binary sensor."""

    unique_id_suffix = "carbon_monoxide"
    update_key = "carbonmonoxide"
    value_attr = "carbon_monoxide"

    _attr_device_class = BinarySensorDeviceClass.CO


class DeconzFireBinarySensor(DeconzBinarySensor[Fire]):
    """Representation of a deCONZ fire binary sensor."""

    unique_id_suffix = "fire"
    update_key = "fire"
    value_attr = "fire"

    _attr_device_class = BinarySensorDeviceClass.SMOKE


class DeconzFireInTestModeBinarySensor(DeconzBinarySensor[Fire]):
    """Representation of a deCONZ fire in-test-mode binary sensor."""

    name_suffix = "Test Mode"
    unique_id_suffix = "in_test_mode"
    old_unique_id_suffix = "test mode"
    update_key = "test"
    value_attr = "in_test_mode"

    _attr_device_class = BinarySensorDeviceClass.SMOKE
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class DeconzFlagBinarySensor(DeconzBinarySensor[GenericFlag]):
    """Representation of a deCONZ generic flag binary sensor."""

    unique_id_suffix = "flag"
    update_key = "flag"
    value_attr = "flag"


class DeconzOpenCloseBinarySensor(DeconzBinarySensor[OpenClose]):
    """Representation of a deCONZ open/close binary sensor."""

    unique_id_suffix = "open"
    update_key = "open"
    value_attr = "open"

    _attr_device_class = BinarySensorDeviceClass.OPENING


class DeconzPresenceBinarySensor(DeconzBinarySensor[Presence]):
    """Representation of a deCONZ presence binary sensor."""

    unique_id_suffix = "presence"
    update_key = "presence"
    value_attr = "presence"

    _attr_device_class = BinarySensorDeviceClass.MOTION


class DeconzVibrationBinarySensor(DeconzBinarySensor[Vibration]):
    """Representation of a deCONZ vibration binary sensor."""

    unique_id_suffix = "vibration"
    update_key = "vibration"
    value_attr = "vibration"

    _attr_device_class = BinarySensorDeviceClass.VIBRATION


class DeconzWaterBinarySensor(DeconzBinarySensor[Water]):
    """Representation of a deCONZ water binary sensor."""

    unique_id_suffix = "water"
    update_key = "water"
    value_attr = "water"

    _attr_device_class = BinarySensorDeviceClass.MOISTURE


class DeconzTamperedCommonBinarySensor(DeconzBinarySensor[SensorResources]):
    """Representation of a deCONZ tampered binary sensor."""

    name_suffix = "Tampered"
    unique_id_suffix = "tampered"
    old_unique_id_suffix = "tampered"
    update_key = "tampered"
    value_attr = "tampered"

    _attr_device_class = BinarySensorDeviceClass.TAMPER
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class DeconzLowBatteryCommonBinarySensor(DeconzBinarySensor[SensorResources]):
    """Representation of a deCONZ low battery binary sensor."""

    name_suffix = "Low Battery"
    unique_id_suffix = "low_battery"
    old_unique_id_suffix = "low battery"
    update_key = "lowbattery"
    value_attr = "low_battery"

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC


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
