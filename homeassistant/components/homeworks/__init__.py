"""Support for Lutron Homeworks Series 4 and 8 systems."""
import logging

from pyhomeworks.pyhomeworks import HW_BUTTON_PRESSED, HW_BUTTON_RELEASED, Homeworks
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DOMAIN = "homeworks"

HOMEWORKS_CONTROLLER = "homeworks"
EVENT_BUTTON_PRESS = "homeworks_button_press"
EVENT_BUTTON_RELEASE = "homeworks_button_release"

CONF_DIMMERS = "dimmers"
CONF_KEYPADS = "keypads"
CONF_ADDR = "addr"
CONF_RATE = "rate"

FADE_RATE = 1.0

CV_FADE_RATE = vol.All(vol.Coerce(float), vol.Range(min=0, max=20))

DIMMER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ADDR): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_RATE, default=FADE_RATE): CV_FADE_RATE,
    }
)

KEYPAD_SCHEMA = vol.Schema(
    {vol.Required(CONF_ADDR): cv.string, vol.Required(CONF_NAME): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT): cv.port,
                vol.Required(CONF_DIMMERS): vol.All(cv.ensure_list, [DIMMER_SCHEMA]),
                vol.Optional(CONF_KEYPADS, default=[]): vol.All(
                    cv.ensure_list, [KEYPAD_SCHEMA]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, base_config: ConfigType) -> bool:
    """Start Homeworks controller."""

    def hw_callback(msg_type, values):
        """Dispatch state changes."""
        _LOGGER.debug("callback: %s, %s", msg_type, values)
        addr = values[0]
        signal = f"homeworks_entity_{addr}"
        dispatcher_send(hass, signal, msg_type, values)

    config = base_config[DOMAIN]
    controller = Homeworks(config[CONF_HOST], config[CONF_PORT], hw_callback)
    hass.data[HOMEWORKS_CONTROLLER] = controller

    def cleanup(event):
        controller.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)

    dimmers = config[CONF_DIMMERS]
    load_platform(hass, Platform.LIGHT, DOMAIN, {CONF_DIMMERS: dimmers}, base_config)

    for key_config in config[CONF_KEYPADS]:
        addr = key_config[CONF_ADDR]
        name = key_config[CONF_NAME]
        HomeworksKeypadEvent(hass, addr, name)

    return True


class HomeworksDevice:
    """Base class of a Homeworks device."""

    def __init__(self, controller, addr, name):
        """Initialize Homeworks device."""
        self._addr = addr
        self._name = name
        self._controller = controller

    @property
    def unique_id(self):
        """Return a unique identifier."""
        return f"homeworks.{self._addr}"

    @property
    def name(self):
        """Device name."""
        return self._name

    @property
    def should_poll(self):
        """No need to poll."""
        return False


class HomeworksKeypadEvent:
    """When you want signals instead of entities.

    Stateless sensors such as keypads are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, hass, addr, name):
        """Register callback that will be used for signals."""
        self._hass = hass
        self._addr = addr
        self._name = name
        self._id = slugify(self._name)
        signal = f"homeworks_entity_{self._addr}"
        async_dispatcher_connect(self._hass, signal, self._update_callback)

    @callback
    def _update_callback(self, msg_type, values):
        """Fire events if button is pressed or released."""

        if msg_type == HW_BUTTON_PRESSED:
            event = EVENT_BUTTON_PRESS
        elif msg_type == HW_BUTTON_RELEASED:
            event = EVENT_BUTTON_RELEASE
        else:
            return
        data = {CONF_ID: self._id, CONF_NAME: self._name, "button": values[1]}
        self._hass.bus.async_fire(event, data)
