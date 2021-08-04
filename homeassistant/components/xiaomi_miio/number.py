"""Motor speed support for Xiaomi Mi Air Humidifier."""
from dataclasses import dataclass
from enum import Enum

from homeassistant.components.number import NumberEntity
from homeassistant.core import callback

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    FEATURE_SET_MOTOR_SPEED,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA4,
)
from .device import XiaomiCoordinatedMiioEntity

ATTR_MOTOR_SPEED = "motor_speed"


@dataclass
class NumberType:
    """Class that holds device specific info for a xiaomi aqara or humidifier number controller types."""

    name: str = None
    short_name: str = None
    unit_of_measurement: str = None
    icon: str = None
    device_class: str = None
    min: float = None
    max: float = None
    step: float = None
    available_with_device_off: bool = True


NUMBER_TYPES = {
    FEATURE_SET_MOTOR_SPEED: NumberType(
        name="Motor Speed",
        icon="mdi:fast-forward-outline",
        short_name=ATTR_MOTOR_SPEED,
        unit_of_measurement="rpm",
        min=200,
        max=2000,
        step=10,
        available_with_device_off=False,
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Selectors from a config entry."""
    entities = []
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return
    model = config_entry.data[CONF_MODEL]
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]

    if model not in [MODEL_AIRHUMIDIFIER_CA4]:
        return

    for number in NUMBER_TYPES.values():
        entities.append(
            XiaomiAirHumidifierNumber(
                f"{config_entry.title} {number.name}",
                device,
                config_entry,
                f"{number.short_name}_{config_entry.unique_id}",
                number,
                coordinator,
            )
        )

    async_add_entities(entities)


class XiaomiAirHumidifierNumber(XiaomiCoordinatedMiioEntity, NumberEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, number, coordinator):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)
        self._attr_icon = number.icon
        self._attr_unit_of_measurement = number.unit_of_measurement
        self._attr_min_value = number.min
        self._attr_max_value = number.max
        self._attr_step = number.step
        self._controller = number
        self._attr_value = self._extract_value_from_attribute(
            self.coordinator.data, self._controller.short_name
        )

    @property
    def available(self):
        """Return the number controller availability."""
        if (
            super().available
            and not self.coordinator.data.is_on
            and not self._controller.available_with_device_off
        ):
            return False
        return super().available

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def async_set_value(self, value):
        """Set an option of the miio device."""
        if (
            self.min_value
            and value < self.min_value
            or self.max_value
            and value > self.max_value
        ):
            raise ValueError(
                f"Value {value} not a valid {self.name} within the range {self.min_value} - {self.max_value}"
            )
        if await self.async_set_motor_speed(value):
            self._attr_value = value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        self._attr_value = self._extract_value_from_attribute(
            self.coordinator.data, self._controller.short_name
        )
        self.async_write_ha_state()

    async def async_set_motor_speed(self, motor_speed: int = 400):
        """Set the target motor speed."""
        return await self._try_command(
            "Setting the target motor speed of the miio device failed.",
            self._device.set_speed,
            motor_speed,
        )
