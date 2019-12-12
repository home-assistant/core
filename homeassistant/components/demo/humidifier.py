"""Demo platform that offers a fake humidifier device."""
from homeassistant.components.humidifier import HumidifierDevice
from homeassistant.components.humidifier.const import (
    CURRENT_HUMIDIFIER_DRY,
    CURRENT_HUMIDIFIER_HUMIDIFY,
    OPERATION_MODE_DRY,
    OPERATION_MODE_HUMIDIFY,
    OPERATION_MODE_HUMIDIFY_DRY,
    OPERATION_MODE_OFF,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TEMPERATURE,
    SUPPORT_WATER_LEVEL,
)

SUPPORT_FLAGS = 0


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo humidifier devices."""
    async_add_entities(
        [
            DemoHumidifier(
                name="Humidifier",
                preset=None,
                fan_mode=None,
                aux=None,
                target_humidity=68,
                current_humidity=77,
                operation_mode=OPERATION_MODE_HUMIDIFY,
                humidifier_action=CURRENT_HUMIDIFIER_HUMIDIFY,
                operation_modes=[OPERATION_MODE_HUMIDIFY, OPERATION_MODE_OFF],
            ),
            DemoHumidifier(
                name="Dehumidifier",
                preset=None,
                fan_mode="On High",
                aux=False,
                target_humidity=54,
                current_humidity=67,
                operation_mode=OPERATION_MODE_DRY,
                humidifier_action=CURRENT_HUMIDIFIER_DRY,
                operation_modes=[OPERATION_MODE_DRY, OPERATION_MODE_OFF],
                current_temperature=25,
                water_level=30,
            ),
            DemoHumidifier(
                name="Hygrostat",
                preset="home",
                preset_modes=["home", "eco"],
                fan_mode="Auto Low",
                aux=None,
                target_humidity=50,
                current_humidity=49,
                operation_mode=OPERATION_MODE_HUMIDIFY_DRY,
                humidifier_action=None,
                operation_modes=[
                    OPERATION_MODE_HUMIDIFY_DRY,
                    OPERATION_MODE_DRY,
                    OPERATION_MODE_HUMIDIFY,
                ],
            ),
        ]
    )


class DemoHumidifier(HumidifierDevice):
    """Representation of a demo humidifier device."""

    def __init__(
        self,
        name,
        preset,
        fan_mode,
        aux,
        target_humidity,
        current_humidity,
        operation_mode,
        humidifier_action,
        operation_modes,
        current_temperature=None,
        preset_modes=None,
        water_level=None,
    ):
        """Initialize the humidifier device."""
        self._name = name
        self._support_flags = SUPPORT_FLAGS
        if preset is not None:
            self._support_flags = self._support_flags | SUPPORT_PRESET_MODE
        if fan_mode is not None:
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE
        if current_temperature is not None:
            self._support_flags = self._support_flags | SUPPORT_TEMPERATURE
        if water_level is not None:
            self._support_flags = self._support_flags | SUPPORT_WATER_LEVEL
        if aux is not None:
            self._support_flags = self._support_flags | SUPPORT_AUX_HEAT
        self._target_humidity = target_humidity
        self._preset = preset
        self._preset_modes = preset_modes
        self._current_humidity = current_humidity
        self._current_temperature = current_temperature
        self._current_fan_mode = fan_mode
        self._fan_modes = ["On Low", "On High", "Auto Low", "Auto High", "Off"]
        self._aux = aux
        self._humidifier_action = humidifier_action
        self._operation_mode = operation_mode
        self._operation_modes = operation_modes
        self._water_level = water_level

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the humidity device."""
        return self._name

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def humidifier_action(self):
        """Return current operation ie. heat, cool, idle."""
        return self._humidifier_action

    @property
    def operation_mode(self):
        """Return humidifier target humidifier state."""
        return self._operation_mode

    @property
    def operation_modes(self):
        """Return the list of available operation modes."""
        return self._operation_modes

    @property
    def preset_mode(self):
        """Return preset mode."""
        return self._preset

    @property
    def preset_modes(self):
        """Return preset modes."""
        return self._preset_modes

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_modes

    @property
    def is_aux_heat(self):
        """Return true if aux heat is on."""
        return self._aux

    @property
    def water_level(self):
        """Return the current water level."""
        return self._water_level

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self._current_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._operation_mode = operation_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Update preset_mode on."""
        self._preset = preset_mode
        self.async_write_ha_state()

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._aux = True
        self.async_write_ha_state()

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._aux = False
        self.async_write_ha_state()
