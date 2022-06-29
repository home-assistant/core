"""Support for deCONZ binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydeconz.interfaces.sensors import SensorResources
from pydeconz.models.event import EventType
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
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import ATTR_DARK, ATTR_ON, DOMAIN as DECONZ_DOMAIN
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

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


@dataclass
class DeconzBinarySensorDescriptionMixin:
    """Required values when describing secondary sensor attributes."""

    suffix: str
    update_key: str
    value_fn: Callable[[SensorResources], bool | None]


@dataclass
class DeconzBinarySensorDescription(
    BinarySensorEntityDescription,
    DeconzBinarySensorDescriptionMixin,
):
    """Class describing deCONZ binary sensor entities."""


ENTITY_DESCRIPTIONS = {
    Alarm: [
        DeconzBinarySensorDescription(
            key="alarm",
            value_fn=lambda device: device.alarm if isinstance(device, Alarm) else None,
            suffix="",
            update_key="alarm",
            device_class=BinarySensorDeviceClass.SAFETY,
        )
    ],
    CarbonMonoxide: [
        DeconzBinarySensorDescription(
            key="carbon_monoxide",
            value_fn=lambda device: device.carbon_monoxide
            if isinstance(device, CarbonMonoxide)
            else None,
            suffix="",
            update_key="carbonmonoxide",
            device_class=BinarySensorDeviceClass.CO,
        )
    ],
    Fire: [
        DeconzBinarySensorDescription(
            key="fire",
            value_fn=lambda device: device.fire if isinstance(device, Fire) else None,
            suffix="",
            update_key="fire",
            device_class=BinarySensorDeviceClass.SMOKE,
        ),
        DeconzBinarySensorDescription(
            key="in_test_mode",
            value_fn=lambda device: device.in_test_mode
            if isinstance(device, Fire)
            else None,
            suffix="Test Mode",
            update_key="test",
            device_class=BinarySensorDeviceClass.SMOKE,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ],
    GenericFlag: [
        DeconzBinarySensorDescription(
            key="flag",
            value_fn=lambda device: device.flag
            if isinstance(device, GenericFlag)
            else None,
            suffix="",
            update_key="flag",
        )
    ],
    OpenClose: [
        DeconzBinarySensorDescription(
            key="open",
            value_fn=lambda device: device.open
            if isinstance(device, OpenClose)
            else None,
            suffix="",
            update_key="open",
            device_class=BinarySensorDeviceClass.OPENING,
        )
    ],
    Presence: [
        DeconzBinarySensorDescription(
            key="presence",
            value_fn=lambda device: device.presence
            if isinstance(device, Presence)
            else None,
            suffix="",
            update_key="presence",
            device_class=BinarySensorDeviceClass.MOTION,
        )
    ],
    Vibration: [
        DeconzBinarySensorDescription(
            key="vibration",
            value_fn=lambda device: device.vibration
            if isinstance(device, Vibration)
            else None,
            suffix="",
            update_key="vibration",
            device_class=BinarySensorDeviceClass.VIBRATION,
        )
    ],
    Water: [
        DeconzBinarySensorDescription(
            key="water",
            value_fn=lambda device: device.water if isinstance(device, Water) else None,
            suffix="",
            update_key="water",
            device_class=BinarySensorDeviceClass.MOISTURE,
        )
    ],
}

BINARY_SENSOR_DESCRIPTIONS = [
    DeconzBinarySensorDescription(
        key="tampered",
        value_fn=lambda device: device.tampered,
        suffix="Tampered",
        update_key="tampered",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzBinarySensorDescription(
        key="low_battery",
        value_fn=lambda device: device.low_battery,
        suffix="Low Battery",
        update_key="lowbattery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


@callback
def async_update_unique_id(
    hass: HomeAssistant, unique_id: str, description: DeconzBinarySensorDescription
) -> None:
    """Update unique ID to always have a suffix.

    Introduced with release 2022.7.
    """
    ent_reg = er.async_get(hass)

    new_unique_id = f"{unique_id}-{description.key}"
    if ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, new_unique_id):
        return

    if description.suffix:
        unique_id = f'{unique_id.split("-", 1)[0]}-{description.suffix.lower()}'

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

        if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
            return

        for description in (
            ENTITY_DESCRIPTIONS.get(type(sensor), []) + BINARY_SENSOR_DESCRIPTIONS
        ):
            if (
                not hasattr(sensor, description.key)
                or description.value_fn(sensor) is None
            ):
                continue

            async_update_unique_id(hass, sensor.unique_id, description)

            async_add_entities([DeconzBinarySensor(sensor, gateway, description)])

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors,
    )

    @callback
    def async_reload_clip_sensors() -> None:
        """Load clip sensor sensors from deCONZ."""
        for sensor_id, sensor in gateway.api.sensors.items():
            if sensor.type.startswith("CLIP"):
                async_add_sensor(EventType.ADDED, sensor_id)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_reload_clip_sensors,
            async_reload_clip_sensors,
        )
    )


class DeconzBinarySensor(DeconzDevice, BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    TYPE = DOMAIN
    _device: SensorResources
    entity_description: DeconzBinarySensorDescription

    def __init__(
        self,
        device: SensorResources,
        gateway: DeconzGateway,
        description: DeconzBinarySensorDescription,
    ) -> None:
        """Initialize deCONZ binary sensor."""
        self.entity_description: DeconzBinarySensorDescription = description
        super().__init__(device, gateway)

        if description.suffix:
            self._attr_name = f"{self._device.name} {description.suffix}"

        self._update_keys = {description.update_key, "reachable"}
        if self.entity_description.key in PROVIDES_EXTRA_ATTRIBUTES:
            self._update_keys.update({"on", "state"})

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{super().unique_id}-{self.entity_description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        if self._device.changed_keys.intersection(self._update_keys):
            super().async_update_callback()

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

        if self._device.secondary_temperature is not None:
            attr[ATTR_TEMPERATURE] = self._device.secondary_temperature

        if isinstance(self._device, Presence):

            if self._device.dark is not None:
                attr[ATTR_DARK] = self._device.dark

        elif isinstance(self._device, Vibration):
            attr[ATTR_ORIENTATION] = self._device.orientation
            attr[ATTR_TILTANGLE] = self._device.tilt_angle
            attr[ATTR_VIBRATIONSTRENGTH] = self._device.vibration_strength

        return attr
