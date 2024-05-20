"""Sensors for GoDice device."""

import logging

import godice

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


ROLLED_NUMBER_SENSOR_DESCR = SensorEntityDescription(
    key="rolled_number", state_class=SensorStateClass.MEASUREMENT
)
COLOR_SENSOR_DESCR = SensorEntityDescription(
    key="color",
    device_class=SensorDeviceClass.ENUM,
    options=[color.name for color in godice.Color],
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
    dice = config_entry.runtime_data.dice
    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.data[const.CONF_ADDRESS])},
        name=config_entry.data[const.CONF_NAME],
        manufacturer=MANUFACTURER,
        model=MODEL,
    )

    entities = [
        (DiceColorSensor, COLOR_SENSOR_DESCR),
        (BatteryLevelSensor, BATTERY_SENSOR_DESCR),
        (DiceNumberSensor, ROLLED_NUMBER_SENSOR_DESCR),
    ]

    async_add_entities(
        [
            entity_class(device_info, entity_description, dice)
            for entity_class, entity_description in entities
        ]
    )


class BaseSensor(SensorEntity):
    """Base for concrete sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    dice: godice.Dice

    def __init__(
        self,
        device_info: DeviceInfo,
        entity_description: SensorEntityDescription,
        dice: godice.Dice,
    ) -> None:
        """Set default values."""
        self.entity_description = entity_description
        self.dice = dice
        self._attr_device_info = device_info
        self._attr_unique_id = (
            f"{device_info[const.CONF_NAME]}_{self.entity_description.key}"
        )
        self._attr_translation_key = entity_description.key


class DiceColorSensor(RestoreSensor, BaseSensor):
    """Represents color of a dice (dots)."""

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

    async def async_update(self) -> None:
        """Poll battery level."""
        _LOGGER.debug("Battery level update")
        self._attr_native_value = await self.dice.get_battery_level()


class DiceNumberSensor(BaseSensor):
    """Represents the rolled dice number."""

    async def async_added_to_hass(self) -> None:
        """Subscribe on rolled number events."""
        await self.dice.subscribe_number_notification(self._handle_number_update)

    async def _handle_number_update(
        self, number: int, _stability_descriptor: godice.StabilityDescriptor
    ) -> None:
        """Handle a rolled number event, update the sensor."""
        _LOGGER.debug("Number update: %s", number)
        self._attr_native_value = number
        self.async_write_ha_state()
