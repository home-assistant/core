"""Demo platform that offers a fake water heater device."""
from homeassistant.components.water_heater import (
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT

SUPPORT_FLAGS_HEATER = (
    SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo water_heater devices."""
    async_add_entities(
        [
            DemoWaterHeater("Demo Water Heater", 119, TEMP_FAHRENHEIT, False, "eco"),
            DemoWaterHeater("Demo Water Heater Celsius", 45, TEMP_CELSIUS, True, "eco"),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoWaterHeater(WaterHeaterEntity):
    """Representation of a demo water_heater device."""

    _attr_should_poll = False
    _attr_supported_features = SUPPORT_FLAGS_HEATER

    def __init__(
        self, name, target_temperature, unit_of_measurement, away, current_operation
    ):
        """Initialize the water_heater device."""
        self._attr_name = name
        if target_temperature is not None:
            self._attr_supported_features = (
                self.supported_features | SUPPORT_TARGET_TEMPERATURE
            )
        if away is not None:
            self._attr_supported_features = self.supported_features | SUPPORT_AWAY_MODE
        if current_operation is not None:
            self._attr_supported_features = (
                self.supported_features | SUPPORT_OPERATION_MODE
            )
        self._attr_target_temperature = target_temperature
        self._attr_temperature_unit = unit_of_measurement
        self._attr_is_away_mode_on = away
        self._attr_current_operation = current_operation
        self._attr_operation_list = [
            "eco",
            "electric",
            "performance",
            "high_demand",
            "heat_pump",
            "gas",
            "off",
        ]

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._attr_current_operation = operation_mode
        self.schedule_update_ha_state()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._attr_is_away_mode_on = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._attr_is_away_mode_on = False
        self.schedule_update_ha_state()
