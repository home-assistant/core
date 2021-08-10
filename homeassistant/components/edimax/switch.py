"""Support for Edimax switches."""
from pyedimax.smartplug import SmartPlug
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

DOMAIN = "edimax"

DEFAULT_NAME = "Edimax Smart Plug"
DEFAULT_PASSWORD = "1234"
DEFAULT_USERNAME = "admin"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Find and return Edimax Smart Plugs."""
    host = config.get(CONF_HOST)
    auth = (config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
    name = config.get(CONF_NAME)

    add_entities([SmartPlugSwitch(SmartPlug(host, auth), name)], True)


class SmartPlugSwitch(SwitchEntity):
    """Representation an Edimax Smart Plug switch."""

    def __init__(self, smartplug, name):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name
        self._now_power = None
        self._now_energy_day = None
        self._state = False
        self._supports_power_monitoring = False
        self._info = None
        self._mac = None

    @property
    def unique_id(self):
        """Return the device's MAC address."""
        return self._mac

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._now_power

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self._now_energy_day

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.state = "ON"

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.state = "OFF"

    def update(self):
        """Update edimax switch."""
        if not self._info:
            self._info = self.smartplug.info
            self._mac = self._info["mac"]
            self._supports_power_monitoring = self._info["model"] != "SP1101W"

        if self._supports_power_monitoring:
            try:
                self._now_power = float(self.smartplug.now_power)
            except (TypeError, ValueError):
                self._now_power = None

            try:
                self._now_energy_day = float(self.smartplug.now_energy_day)
            except (TypeError, ValueError):
                self._now_energy_day = None

        self._state = self.smartplug.state == "ON"
