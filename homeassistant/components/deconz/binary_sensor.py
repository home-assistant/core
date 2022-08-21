"""Support for deCONZ binary sensors."""
from __future__ import annotations

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

    name_suffix: str
    unique_id_suffix: str
    update_key: str
    value_attr: str
    old_unique_id_suffix: str


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
            name_suffix="",
            unique_id_suffix="alarm",
            update_key="alarm",
            value_attr="alarm",
            device_class=BinarySensorDeviceClass.SAFETY,
            old_unique_id_suffix="",
        )
    ],
    CarbonMonoxide: [
        DeconzBinarySensorDescription(
            key="carbon_monoxide",
            name_suffix="",
            unique_id_suffix="carbon_monoxide",
            update_key="carbonmonoxide",
            value_attr="carbon_monoxide",
            device_class=BinarySensorDeviceClass.CO,
            old_unique_id_suffix="",
        )
    ],
    Fire: [
        DeconzBinarySensorDescription(
            key="fire",
            name_suffix="",
            unique_id_suffix="fire",
            update_key="fire",
            value_attr="fire",
            device_class=BinarySensorDeviceClass.SMOKE,
            old_unique_id_suffix="",
        ),
        DeconzBinarySensorDescription(
            key="in_test_mode",
            name_suffix="Test Mode",
            unique_id_suffix="in_test_mode",
            update_key="test",
            value_attr="in_test_mode",
            device_class=BinarySensorDeviceClass.SMOKE,
            entity_category=EntityCategory.DIAGNOSTIC,
            old_unique_id_suffix="test mode",
        ),
    ],
    GenericFlag: [
        DeconzBinarySensorDescription(
            key="flag",
            name_suffix="",
            unique_id_suffix="flag",
            update_key="flag",
            value_attr="flag",
            old_unique_id_suffix="",
        )
    ],
    OpenClose: [
        DeconzBinarySensorDescription(
            key="open",
            name_suffix="",
            unique_id_suffix="open",
            update_key="open",
            value_attr="open",
            device_class=BinarySensorDeviceClass.OPENING,
            old_unique_id_suffix="",
        )
    ],
    Presence: [
        DeconzBinarySensorDescription(
            key="presence",
            name_suffix="",
            unique_id_suffix="presence",
            update_key="presence",
            value_attr="presence",
            device_class=BinarySensorDeviceClass.MOTION,
            old_unique_id_suffix="",
        )
    ],
    Vibration: [
        DeconzBinarySensorDescription(
            key="vibration",
            name_suffix="",
            unique_id_suffix="vibration",
            update_key="vibration",
            value_attr="vibration",
            device_class=BinarySensorDeviceClass.VIBRATION,
            old_unique_id_suffix="",
        )
    ],
    Water: [
        DeconzBinarySensorDescription(
            key="water",
            name_suffix="",
            unique_id_suffix="water",
            update_key="water",
            value_attr="water",
            device_class=BinarySensorDeviceClass.MOISTURE,
            old_unique_id_suffix="",
        )
    ],
}

COMMON_DESCRIPTIONS = [
    DeconzBinarySensorDescription(
        key="tampered",
        name_suffix="Tampered",
        unique_id_suffix="tampered",
        update_key="tampered",
        value_attr="tampered",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        old_unique_id_suffix="tampered",
    ),
    DeconzBinarySensorDescription(
        key="low_battery",
        name_suffix="Low Battery",
        unique_id_suffix="low_battery",
        update_key="lowbattery",
        value_attr="low_battery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        old_unique_id_suffix="low battery",
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

    new_unique_id = f"{unique_id}-{description.unique_id_suffix}"
    if ent_reg.async_get_entity_id(DOMAIN, DECONZ_DOMAIN, new_unique_id):
        return

    if description.old_unique_id_suffix:
        unique_id = f'{unique_id.split("-", 1)[0]}-{description.old_unique_id_suffix}'

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

        for description in (
            ENTITY_DESCRIPTIONS.get(type(sensor), []) + COMMON_DESCRIPTIONS
        ):
            if getattr(sensor, description.value_attr) is None:
                continue

            async_update_unique_id(hass, sensor.unique_id, description)

            async_add_entities([DeconzBinarySensor(sensor, gateway, description)])

    gateway.register_platform_add_device_callback(
        async_add_sensor,
        gateway.api.sensors,
    )


class DeconzBinarySensor(DeconzDevice[SensorResources], BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    TYPE = DOMAIN
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

        if description.name_suffix:
            self._attr_name = f"{self._device.name} {description.name_suffix}"

        self._update_keys = {description.update_key, "reachable"}
        if self.entity_description.key in PROVIDES_EXTRA_ATTRIBUTES:
            self._update_keys.update({"on", "state"})

        self._attr_is_on = getattr(device, description.value_attr)

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{super().unique_id}-{self.entity_description.key}"

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        if self._device.changed_keys.intersection(self._update_keys):
            self._attr_is_on = getattr(self._device, self.entity_description.value_attr)
            super().async_update_callback()

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
