"""Sensors for GoDice device."""

import logging

from godice import Color as DiceColor

from homeassistant import const
from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_DEVICE, DATA_DEVICE_INFO, DOMAIN

_LOGGER = logging.getLogger(__name__)


ROLLED_NUMBER_SENSOR_DESCR = SensorEntityDescription(
    key="rolled_number", state_class=SensorStateClass.MEASUREMENT
)
COLOR_SENSOR_DESCR = SensorEntityDescription(
    key="color",
    device_class=SensorDeviceClass.ENUM,
    options=[color.name for color in DiceColor],
)
BATTERY_SENSOR_DESCR = SensorEntityDescription(
    key="battery_level",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=const.PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setups Dice sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    device = data[DATA_DEVICE]
    device_info = data[DATA_DEVICE_INFO]

    entry_ctors = [
        DiceColorSensor,
        BatteryLevelSensor,
        DiceNumberSensor,
    ]

    entries = [ctor(device_info, device) for ctor in entry_ctors]
    async_add_entities(entries)


class BaseSensor(SensorEntity):
    """Base for concrete sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entity_description, device_info) -> None:
        """Set default values."""
        self.entity_description = entity_description
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{device_info[const.CONF_NAME]}_{self.entity_description.key}"
        )
        self._attr_translation_key = entity_description.key


class DiceColorSensor(RestoreSensor, BaseSensor):
    """Represents color of a dice (dots)."""

    def __init__(self, device_info, device) -> None:
        """Set default values."""
        descr = COLOR_SENSOR_DESCR
        super().__init__(descr, device_info)
        self.dice = device

    async def async_added_to_hass(self) -> None:
        """Restore a color value if any, read the value otherwise."""
        last_state = await self.async_get_last_sensor_data()
        if last_state and last_state.native_value is not None:
            self._attr_native_value = last_state.native_value
        else:
            color = await self.dice.get_color()
            self._attr_native_value = color.name


class BatteryLevelSensor(BaseSensor):
    """Represents battery level."""

    _attr_should_poll = True

    def __init__(self, device_info, device) -> None:
        """Set default values."""
        descr = BATTERY_SENSOR_DESCR
        super().__init__(descr, device_info)
        self.dice = device

    async def async_update(self) -> None:
        """Poll battery level."""
        _LOGGER.debug("Battery level update")
        self._attr_native_value = await self.dice.get_battery_level()


class DiceNumberSensor(BaseSensor):
    """Represents the rolled dice number."""

    def __init__(self, device_info, device) -> None:
        """Set default values."""
        descr = ROLLED_NUMBER_SENSOR_DESCR
        super().__init__(descr, device_info)
        self.dice = device

    async def async_added_to_hass(self) -> None:
        """Subscribe on rolled number events."""
        await self.dice.subscribe_number_notification(self._handle_upd)

    async def _handle_upd(self, number, _stability_descr):
        """Handle a rolled number event, update the sensor."""
        _LOGGER.debug("Number update: %s", number)
        self._attr_native_value = number
        self.async_write_ha_state()
