"""Support for a ScreenLogic Water Heater."""
import logging

from screenlogicpy.const import HEAT_MODE

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

HEAD_MODE_NAMES = HEAT_MODE._names  # pylint: disable=protected-access

MODE_NAME_TO_MODE_NUM = {
    HEAD_MODE_NAMES[num]: num for num in range(len(HEAD_MODE_NAMES))
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]

    for body in data["devices"]["water_heater"]:
        _LOGGER.info(body)
        entities.append(ScreenLogicWaterHeater(data["coordinator"], body))
    async_add_entities(entities, True)


class ScreenLogicWaterHeater(ScreenlogicEntity, WaterHeaterEntity):
    """Represents the heating functions for a body of water."""

    @property
    def name(self) -> str:
        """Name of the water heater."""
        ent_name = self.body["heat_status"]["name"]
        return f"{self.gateway_name} {ent_name}"

    @property
    def state(self) -> str:
        """State of the water heater."""
        return HEAT_MODE.GetFriendlyName(self.body["heat_status"]["value"])

    @property
    def min_temp(self) -> float:
        """Minimum allowed temperature."""
        return self.body["min_set_point"]["value"]

    @property
    def max_temp(self) -> float:
        """Maximum allowed temperature."""
        return self.body["max_set_point"]["value"]

    @property
    def current_temperature(self) -> float:
        """Return water temperature."""
        return self.body["last_temperature"]["value"]

    @property
    def target_temperature(self) -> float:
        """Target temperature."""
        return self.body["heat_set_point"]["value"]

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        if self.config_data["is_celcius"]["value"] == 1:
            return TEMP_CELSIUS
        return TEMP_FAHRENHEIT

    @property
    def current_operation(self) -> str:
        """Return operation."""
        return HEAT_MODE.GetFriendlyName(self.body["heat_mode"]["value"])

    @property
    def operation_list(self):
        """All available operations."""
        return HEAD_MODE_NAMES

    @property
    def supported_features(self):
        """Supported features of the water heater."""
        return SUPPORTED_FEATURES

    async def async_set_temperature(self, **kwargs) -> None:
        """Change the setpoint of the heater."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if await self.hass.async_add_executor_job(
            self.gateway.set_heat_temp, int(self._data_key), int(temperature)
        ):
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("screenlogic set_temperature error")

    async def async_set_operation_mode(self, operation_mode) -> None:
        """Set the operation mode."""
        mode = MODE_NAME_TO_MODE_NUM[operation_mode]
        if await self.hass.async_add_executor_job(
            self.gateway.set_heat_mode, int(self._data_key), int(mode)
        ):
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("screenlogic set_operation_mode error")

    @property
    def body(self):
        """Shortcut to access body data."""
        return self.bodies_data[self._data_key]

    @property
    def bodies_data(self):
        """Shortcut to access bodies data."""
        return self.coordinator.data["bodies"]
