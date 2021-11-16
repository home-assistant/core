"""Support for deCONZ binary sensors."""
from __future__ import annotations

from collections.abc import ValuesView

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
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_TAMPER,
    DEVICE_CLASS_VIBRATION,
    DOMAIN,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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

ENTITY_DESCRIPTIONS = {
    CarbonMonoxide: BinarySensorEntityDescription(
        key="carbonmonoxide",
        device_class=DEVICE_CLASS_GAS,
    ),
    Fire: BinarySensorEntityDescription(
        key="fire",
        device_class=DEVICE_CLASS_SMOKE,
    ),
    OpenClose: BinarySensorEntityDescription(
        key="openclose",
        device_class=DEVICE_CLASS_OPENING,
    ),
    Presence: BinarySensorEntityDescription(
        key="presence",
        device_class=DEVICE_CLASS_MOTION,
    ),
    Vibration: BinarySensorEntityDescription(
        key="vibration",
        device_class=DEVICE_CLASS_VIBRATION,
    ),
    Water: BinarySensorEntityDescription(
        key="water",
        device_class=DEVICE_CLASS_MOISTURE,
    ),
}


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
        entities: list[DeconzBinarySensor | DeconzTampering] = []

        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if (
                isinstance(sensor, DECONZ_BINARY_SENSORS)
                and sensor.unique_id not in gateway.entities[DOMAIN]
            ):
                entities.append(DeconzBinarySensor(sensor, gateway))

            if sensor.tampered is not None:
                known_tampering_sensors = set(gateway.entities[DOMAIN])
                new_tampering_sensor = DeconzTampering(sensor, gateway)
                if new_tampering_sensor.unique_id not in known_tampering_sensors:
                    entities.append(new_tampering_sensor)

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


class DeconzTampering(DeconzDevice, BinarySensorEntity):
    """Representation of a deCONZ tampering sensor."""

    TYPE = DOMAIN
    _device: PydeconzSensor

    _attr_entity_category = ENTITY_CATEGORY_DIAGNOSTIC
    _attr_device_class = DEVICE_CLASS_TAMPER

    def __init__(self, device: PydeconzSensor, gateway: DeconzGateway) -> None:
        """Initialize deCONZ binary sensor."""
        super().__init__(device, gateway)

        self._attr_name = f"{self._device.name} Tampered"

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self.serial}-tampered"

    @callback
    def async_update_callback(self) -> None:
        """Update the sensor's state."""
        keys = {"tampered", "reachable"}
        if self._device.changed_keys.intersection(keys):
            super().async_update_callback()

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self._device.tampered  # type: ignore[no-any-return]
