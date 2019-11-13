"""Demo platform that offers a fake humidifier device."""
from homeassistant.components.humidifier import HumidifierDevice
from homeassistant.components.humidifier.const import (
    CURRENT_HUMIDIFIER_DRY,
    CURRENT_HUMIDIFIER_HUMIDIFY,
    HUMIDIFIER_MODE_DRY,
    HUMIDIFIER_MODE_HUMIDIFY,
    HUMIDIFIER_MODE_HUMIDIFY_DRY,
    HUMIDIFIER_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
)

SUPPORT_FLAGS = 0


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo humidifier devices."""
    add_entities(
        [
            DemoHumidifier(
                name="Humidifier",
                preset=None,
                fan_mode=None,
                target_humidity=68,
                current_humidity=77,
                humidifier_mode=HUMIDIFIER_MODE_HUMIDIFY,
                humidifier_action=CURRENT_HUMIDIFIER_HUMIDIFY,
                humidifier_modes=[HUMIDIFIER_MODE_HUMIDIFY, HUMIDIFIER_MODE_OFF],
            ),
            DemoHumidifier(
                name="Dehumidifier",
                preset=None,
                fan_mode="On High",
                target_humidity=54,
                current_humidity=67,
                humidifier_mode=HUMIDIFIER_MODE_DRY,
                humidifier_action=CURRENT_HUMIDIFIER_DRY,
                humidifier_modes=[HUMIDIFIER_MODE_DRY, HUMIDIFIER_MODE_OFF],
            ),
            DemoHumidifier(
                name="Hygrostat",
                preset="home",
                preset_modes=["home", "eco"],
                fan_mode="Auto Low",
                target_humidity=50,
                current_humidity=49,
                humidifier_mode=HUMIDIFIER_MODE_HUMIDIFY_DRY,
                humidifier_action=None,
                humidifier_modes=[
                    HUMIDIFIER_MODE_HUMIDIFY_DRY,
                    HUMIDIFIER_MODE_DRY,
                    HUMIDIFIER_MODE_HUMIDIFY,
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
        target_humidity,
        current_humidity,
        humidifier_mode,
        humidifier_action,
        humidifier_modes,
        preset_modes=None,
    ):
        """Initialize the humidifier device."""
        self._name = name
        self._support_flags = SUPPORT_FLAGS
        if preset is not None:
            self._support_flags = self._support_flags | SUPPORT_PRESET_MODE
        if fan_mode is not None:
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE
        if target_humidity is not None:
            self._support_flags = self._support_flags | SUPPORT_TARGET_HUMIDITY
        self._target_humidity = target_humidity
        self._preset = preset
        self._preset_modes = preset_modes
        self._current_humidity = current_humidity
        self._current_fan_mode = fan_mode
        self._fan_modes = ["On Low", "On High", "Auto Low", "Auto High", "Off"]
        self._humidifier_action = humidifier_action
        self._humidifier_mode = humidifier_mode
        self._humidifier_modes = humidifier_modes

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
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def humidifier_action(self):
        """Return current operation ie. heat, cool, idle."""
        return self._humidifier_action

    @property
    def humidifier_mode(self):
        """Return humidifier target humidifier state."""
        return self._humidifier_mode

    @property
    def humidifier_modes(self):
        """Return the list of available operation modes."""
        return self._humidifier_modes

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

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        self._current_fan_mode = fan_mode
        self.async_write_ha_state()

    async def async_set_humidifier_mode(self, humidifier_mode):
        """Set new operation mode."""
        self._humidifier_mode = humidifier_mode
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Update preset_mode on."""
        self._preset = preset_mode
        self.async_write_ha_state()
