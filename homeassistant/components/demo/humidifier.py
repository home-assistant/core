"""Demo platform that offers a fake humidifier device."""
from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
)

SUPPORT_FLAGS = 0


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Demo humidifier devices."""
    async_add_entities(
        [
            DemoHumidifier(
                name="Humidifier",
                mode=None,
                target_humidity=68,
                device_class=DEVICE_CLASS_HUMIDIFIER,
            ),
            DemoHumidifier(
                name="Dehumidifier",
                mode=None,
                target_humidity=54,
                device_class=DEVICE_CLASS_DEHUMIDIFIER,
            ),
            DemoHumidifier(
                name="Hygrostat",
                mode="home",
                available_modes=["home", "eco"],
                target_humidity=50,
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo humidifier devices config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoHumidifier(HumidifierEntity):
    """Representation of a demo humidifier device."""

    def __init__(
        self,
        name,
        mode,
        target_humidity,
        available_modes=None,
        is_on=True,
        device_class=None,
    ):
        """Initialize the humidifier device."""
        self._name = name
        self._state = is_on
        self._support_flags = SUPPORT_FLAGS
        if mode is not None:
            self._support_flags = self._support_flags | SUPPORT_MODES
        self._target_humidity = target_humidity
        self._mode = mode
        self._available_modes = available_modes
        self._device_class = device_class

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
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def mode(self):
        """Return current mode."""
        return self._mode

    @property
    def available_modes(self):
        """Return available modes."""
        return self._available_modes

    @property
    def is_on(self):
        """Return true if the humidifier is on."""
        return self._state

    @property
    def device_class(self):
        """Return the device class of the humidifier."""
        return self._device_class

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self.async_write_ha_state()

    async def async_set_humidity(self, humidity):
        """Set new humidity level."""
        self._target_humidity = humidity
        self.async_write_ha_state()

    async def async_set_mode(self, mode):
        """Update mode."""
        self._mode = mode
        self.async_write_ha_state()
