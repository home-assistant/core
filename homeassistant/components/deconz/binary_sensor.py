"""Support for deCONZ binary sensors."""
from __future__ import annotations

from collections.abc import Callable, ValuesView
from dataclasses import dataclass

from pydeconz.sensor import (
    Alarm,
    CarbonMonoxide,
    DeconzBinarySensor as PydeconzBinarySensor,
    DeconzSensor as PydeconzSensor,
    Fire,
    GenericFlag,
    OpenClose,
    Presence,
    Vibration,
    Water,
)

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

from .const import ATTR_DARK, ATTR_ON
from .deconz_device import DeconzDevice
from .gateway import DeconzGateway, get_gateway_from_config_entry

DECONZ_BINARY_SENSORS = (
    Alarm,
    CarbonMonoxide,
    Fire,
    GenericFlag,
    OpenClose,
    Presence,
    Vibration,
    Water,
)

ATTR_ORIENTATION = "orientation"
ATTR_TILTANGLE = "tiltangle"
ATTR_VIBRATIONSTRENGTH = "vibrationstrength"


@dataclass
class DeconzBinarySensorDescriptionMixin:
    """Required values when describing secondary sensor attributes."""

    suffix: str
    update_key: str
    required_attr: str
    value_fn: Callable[[PydeconzSensor], bool | None]


@dataclass
class DeconzBinarySensorDescription(
    BinarySensorEntityDescription,
    DeconzBinarySensorDescriptionMixin,
):
    """Class describing deCONZ binary sensor entities."""


ENTITY_DESCRIPTIONS = {
    Alarm: BinarySensorEntityDescription(
        key="alarm",
        device_class=BinarySensorDeviceClass.SAFETY,
    ),
    CarbonMonoxide: BinarySensorEntityDescription(
        key="carbonmonoxide",
        device_class=BinarySensorDeviceClass.CO,
    ),
    Fire: BinarySensorEntityDescription(
        key="fire",
        device_class=BinarySensorDeviceClass.SMOKE,
    ),
    OpenClose: BinarySensorEntityDescription(
        key="openclose",
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    Presence: BinarySensorEntityDescription(
        key="presence",
        device_class=BinarySensorDeviceClass.MOTION,
    ),
    Vibration: BinarySensorEntityDescription(
        key="vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
    ),
    Water: BinarySensorEntityDescription(
        key="water",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
}


BINARY_SENSOR_DESCRIPTIONS = [
    DeconzBinarySensorDescription(
        key="tamper",
        required_attr="tampered",
        value_fn=lambda device: device.tampered,
        suffix="Tampered",
        update_key="tampered",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzBinarySensorDescription(
        key="low_battery",
        required_attr="low_battery",
        value_fn=lambda device: device.low_battery,
        suffix="Low Battery",
        update_key="lowbattery",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DeconzBinarySensorDescription(
        key="in_test_mode",
        required_attr="in_test_mode",
        value_fn=lambda device: device.in_test_mode,
        suffix="Test Mode",
        update_key="test",
        device_class=BinarySensorDeviceClass.SMOKE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ binary sensor."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_sensor(
        sensors: list[PydeconzSensor]
        | ValuesView[PydeconzSensor] = gateway.api.sensors.values(),
    ) -> None:
        """Add binary sensor from deCONZ."""
        entities: list[DeconzBinarySensor | DeconzPropertyBinarySensor] = []

        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if (
                isinstance(sensor, DECONZ_BINARY_SENSORS)
                and sensor.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzBinarySensor(sensor, gateway))

            known_sensor_entities = set(gateway.entities[DOMAIN])
            for sensor_description in BINARY_SENSOR_DESCRIPTIONS:

                if (
                    not hasattr(sensor, sensor_description.required_attr)
                    or sensor_description.value_fn(sensor) is None
                ):
                    continue

                new_sensor = DeconzPropertyBinarySensor(
                    sensor, gateway, sensor_description
                )
                if new_sensor.unique_id not in known_sensor_entities:
                    entities.append(new_sensor)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_sensor,
            async_add_sensor,
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


class DeconzBinarySensor(DeconzDevice, BinarySensorEntity):
    """Representation of a deCONZ binary sensor."""

    TYPE = DOMAIN
    _device: PydeconzBinarySensor

    def __init__(self, device: PydeconzBinarySensor, gateway: DeconzGateway) -> None:
        """Initialize deCONZ binary sensor."""
        super().__init__(device, gateway)

        if entity_description := ENTITY_DESCRIPTIONS.get(type(device)):
            self.entity_description = entity_description

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        keys = {"on", "reachable", "state"}
        if self._device.changed_keys.intersection(keys):
            super().async_update_callback()

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        return self._device.state  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, bool | float | int | list | None]:
        """Return the state attributes of the sensor."""
        attr: dict[str, bool | float | int | list | None] = {}

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


class DeconzPropertyBinarySensor(DeconzDevice, BinarySensorEntity):
    """Representation of a deCONZ Property sensor."""

    TYPE = DOMAIN
    _device: PydeconzSensor
    entity_description: DeconzBinarySensorDescription

    def __init__(
        self,
        device: PydeconzSensor,
        gateway: DeconzGateway,
        description: DeconzBinarySensorDescription,
    ) -> None:
        """Initialize deCONZ binary sensor."""
        self.entity_description = description
        super().__init__(device, gateway)

        self._attr_name = f"{self._device.name} {description.suffix}"
        self._update_keys = {description.update_key, "reachable"}

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self.serial}-{self.entity_description.suffix.lower()}"

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        if self._device.changed_keys.intersection(self._update_keys):
            super().async_update_callback()

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)
