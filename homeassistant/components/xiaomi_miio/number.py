"""Motor speed support for Xiaomi Mi Air Humidifier."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
class XiaomiMiioNumberDescription(NumberEntityDescription):
    """A class that describes number entities."""

    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    available_with_device_off: bool = True


NUMBER_TYPES = {
    FEATURE_SET_MOTOR_SPEED: XiaomiMiioNumberDescription(
        key=ATTR_MOTOR_SPEED,
        name="Motor Speed",
        icon="mdi:fast-forward-outline",
        unit_of_measurement="rpm",
        min_value=200,
        max_value=2000,
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

    if model != MODEL_AIRHUMIDIFIER_CA4:
        return

    description = NUMBER_TYPES[FEATURE_SET_MOTOR_SPEED]
    entities.append(
        XiaomiAirHumidifierNumber(
            f"{config_entry.title} {description.name}",
            device,
            config_entry,
            f"{description.key}_{config_entry.unique_id}",
            hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR],
            description,
        )
    )

    async_add_entities(entities)


class XiaomiAirHumidifierNumber(XiaomiCoordinatedMiioEntity, NumberEntity):
    """Representation of a generic Xiaomi attribute selector."""

    def __init__(self, name, device, entry, unique_id, coordinator, description):
        """Initialize the generic Xiaomi attribute selector."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._attr_min_value = description.min_value
        self._attr_max_value = description.max_value
        self._attr_step = description.step
        self._attr_value = self._extract_value_from_attribute(
            coordinator.data, description.key
        )
        self.entity_description = description

    @property
    def available(self):
        """Return the number controller availability."""
        if (
            super().available
            and not self.coordinator.data.is_on
            and not self.entity_description.available_with_device_off
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
        if await self.async_set_motor_speed(value):
            self._attr_value = value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        self._attr_value = self._extract_value_from_attribute(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    async def async_set_motor_speed(self, motor_speed: int = 400):
        """Set the target motor speed."""
        return await self._try_command(
            "Setting the target motor speed of the miio device failed.",
            self._device.set_speed,
            motor_speed,
        )
