"""Support for Vera sensors."""
from datetime import timedelta
from typing import Callable, List, Optional, cast

import pyvera as veraApi

from homeassistant.components.sensor import DOMAIN as PLATFORM_DOMAIN, ENTITY_ID_FORMAT
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import LIGHT_LUX, PERCENTAGE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import convert

from . import VeraDevice
from .common import ControllerData, get_controller_data

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraSensor(device, controller_data)
            for device in controller_data.devices.get(PLATFORM_DOMAIN)
        ],
        True,
    )


class VeraSensor(VeraDevice[veraApi.VeraSensor], Entity):
    """Representation of a Vera Sensor."""

    def __init__(
        self, vera_device: veraApi.VeraSensor, controller_data: ControllerData
    ):
        """Initialize the sensor."""
        self.current_value = None
        self._temperature_units = None
        self.last_changed_time = None
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def state(self) -> str:
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""

        if self.vera_device.category == veraApi.CATEGORY_TEMPERATURE_SENSOR:
            return self._temperature_units
        if self.vera_device.category == veraApi.CATEGORY_LIGHT_SENSOR:
            return LIGHT_LUX
        if self.vera_device.category == veraApi.CATEGORY_UV_SENSOR:
            return "level"
        if self.vera_device.category == veraApi.CATEGORY_HUMIDITY_SENSOR:
            return PERCENTAGE
        if self.vera_device.category == veraApi.CATEGORY_POWER_METER:
            return "watts"

    def update(self) -> None:
        """Update the state."""

        if self.vera_device.category == veraApi.CATEGORY_TEMPERATURE_SENSOR:
            self.current_value = self.vera_device.temperature

            vera_temp_units = self.vera_device.vera_controller.temperature_units

            if vera_temp_units == "F":
                self._temperature_units = TEMP_FAHRENHEIT
            else:
                self._temperature_units = TEMP_CELSIUS

        elif self.vera_device.category == veraApi.CATEGORY_LIGHT_SENSOR:
            self.current_value = self.vera_device.light
        elif self.vera_device.category == veraApi.CATEGORY_UV_SENSOR:
            self.current_value = self.vera_device.light
        elif self.vera_device.category == veraApi.CATEGORY_HUMIDITY_SENSOR:
            self.current_value = self.vera_device.humidity
        elif self.vera_device.category == veraApi.CATEGORY_SCENE_CONTROLLER:
            controller = cast(veraApi.VeraSceneController, self.vera_device)
            value = controller.get_last_scene_id(True)
            time = controller.get_last_scene_time(True)
            if time == self.last_changed_time:
                self.current_value = None
            else:
                self.current_value = value
            self.last_changed_time = time
        elif self.vera_device.category == veraApi.CATEGORY_POWER_METER:
            power = convert(self.vera_device.power, float, 0)
            self.current_value = int(round(power, 0))
        elif self.vera_device.is_trippable:
            tripped = self.vera_device.is_tripped
            self.current_value = "Tripped" if tripped else "Not Tripped"
        else:
            self.current_value = "Unknown"
