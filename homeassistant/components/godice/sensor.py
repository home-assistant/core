"""Sensors for GoDice device."""

import logging

from godice import Color as DiceColor

from homeassistant import const
from homeassistant.components import persistent_notification
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

from .const import DOMAIN
from .dice import ConnectionState, DiceConnectionObserver

_LOGGER = logging.getLogger(__name__)


ROLLED_NUMBER_SENSOR_DESCR = SensorEntityDescription(
    key="rolled_number", state_class=SensorStateClass.MEASUREMENT
)
COLOR_SENSOR_DESCR = SensorEntityDescription(
    key="color",
    device_class=SensorDeviceClass.ENUM,
    options=[color.name for color in DiceColor],
)
CONNECTION_SENSOR_DESCR = SensorEntityDescription(
    key="connection",
    device_class=SensorDeviceClass.ENUM,
    options=[state.name for state in ConnectionState],
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
    device = data["device"]
    devinfo = data["device_info"]

    entry_ctors = [
        DiceConnectionSensor,
        DiceColorSensor,
        BatteryLevelSensor,
        DiceNumberSensor,
    ]

    entries = [ctor(devinfo, device) for ctor in entry_ctors]
    async_add_entities(entries)


class BaseSensor(SensorEntity, DiceConnectionObserver):
    """Base for concrete sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, entity_description, devinfo) -> None:
        """Set default values."""
        self.entity_description = entity_description
        self._attr_device_info = devinfo
        self._attr_unique_id = f"{devinfo['name']}_{self.entity_description.key}"
        self._attr_translation_key = entity_description.key


class DiceConnectionSensor(BaseSensor):
    """Represents connection state."""

    def __init__(self, devinfo, device) -> None:
        """Set default values."""
        descr = CONNECTION_SENSOR_DESCR
        super().__init__(descr, devinfo)
        self.dice = device

    async def async_added_to_hass(self) -> None:
        """Subscribe on connection state events."""
        await self.dice.subscribe_connection_notification(self._handle_conn_update)

    async def _handle_conn_update(self, conn_state):
        self._attr_native_value = conn_state.name
        self.async_write_ha_state()

        if conn_state == ConnectionState.CONNECTED:
            await self.dice.pulse_led(2, 50, 20, (0, 255, 0))
        elif conn_state == ConnectionState.CONNECTING:
            persistent_notification.async_create(
                self.hass,
                "Connection to GoDice lost, reconnecting. Make sure GoDice is charged and move it closer to the hub.",
                title="GoDice connection is lost",
            )
        elif conn_state == ConnectionState.DISCONNECTED:
            persistent_notification.async_create(
                self.hass,
                "Could not find GoDice. Keep it closer to the hub or consider setting up a bluetooth-proxy. Reload the integration once ready",
                title="GoDice disconnected",
            )


class DiceColorSensor(RestoreSensor, BaseSensor):
    """Represents color of a dice (dots)."""

    def __init__(self, devinfo, device) -> None:
        """Set default values."""
        descr = COLOR_SENSOR_DESCR
        super().__init__(descr, devinfo)
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

    def __init__(self, devinfo, device) -> None:
        """Set default values."""
        descr = BATTERY_SENSOR_DESCR
        super().__init__(descr, devinfo)
        self.dice = device

    async def async_update(self) -> None:
        """Poll battery level."""
        _LOGGER.debug("Update battery level")
        self._attr_native_value = await self.dice.get_battery_level()


class DiceNumberSensor(BaseSensor):
    """Represents the rolled dice number."""

    def __init__(self, devinfo, device) -> None:
        """Set default values."""
        descr = ROLLED_NUMBER_SENSOR_DESCR
        super().__init__(descr, devinfo)
        self.dice = device

    async def async_added_to_hass(self) -> None:
        """Subscribe on rolled number events."""
        await self.dice.subscribe_number_notification(self._handle_upd)

    async def _handle_upd(self, number, _stability_descr):
        """Handle a rolled number event, update the sensor."""
        _LOGGER.debug("Number update: %s", number)
        self._attr_native_value = number
        self.async_write_ha_state()
