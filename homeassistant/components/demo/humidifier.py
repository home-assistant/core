"""Demo platform that offers a fake humidifier device."""
from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import SUPPORT_PRESET_MODE

SUPPORT_FLAGS = 0


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo humidifier devices."""
    async_add_entities(
        [
            DemoHumidifier(
                name="Humidifier", preset=None, target_humidity=68, current_humidity=77,
            ),
            DemoHumidifier(
                name="Dehumidifier",
                preset=None,
                target_humidity=54,
                current_humidity=67,
            ),
            DemoHumidifier(
                name="Hygrostat",
                preset="home",
                preset_modes=["home", "eco"],
                target_humidity=50,
                current_humidity=49,
            ),
        ]
    )


class DemoHumidifier(HumidifierEntity):
    """Representation of a demo humidifier device."""

    def __init__(
        self,
        name,
        preset,
        target_humidity,
        current_humidity,
        preset_modes=None,
        is_on=True,
    ):
        """Initialize the humidifier device."""
        self._name = name
        self._state = is_on
        self._support_flags = SUPPORT_FLAGS
        if preset is not None:
            self._support_flags = self._support_flags | SUPPORT_PRESET_MODE
        self._target_humidity = target_humidity
        self._preset = preset
        self._preset_modes = preset_modes
        self._current_humidity = current_humidity

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
    def preset_mode(self):
        """Return preset mode."""
        return self._preset

    @property
    def preset_modes(self):
        """Return preset modes."""
        return self._preset_modes

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self):
        """Turn the device on."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the device off."""
        self._state = False
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Update preset_mode on."""
        self._preset = preset_mode
        self.async_write_ha_state()
