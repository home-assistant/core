"""
Support for Vera devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/vera/
"""
import logging
from collections import defaultdict

import voluptuous as vol

from requests.exceptions import RequestException

from homeassistant.util.dt import utc_from_timestamp
from homeassistant.util import convert
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyvera==0.2.20']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vera'

VERA_CONTROLLER = None

CONF_CONTROLLER = 'vera_controller_url'
CONF_EXCLUDE = 'exclude'
CONF_LIGHTS = 'lights'

ATTR_CURRENT_POWER_MWH = "current_power_mwh"

VERA_DEVICES = defaultdict(list)

VERA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CONTROLLER): cv.url,
        vol.Optional(CONF_EXCLUDE, default=[]): VERA_ID_LIST_SCHEMA,
        vol.Optional(CONF_LIGHTS, default=[]): VERA_ID_LIST_SCHEMA
    }),
}, extra=vol.ALLOW_EXTRA)

VERA_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch', 'lock', 'climate', 'cover'
]


# pylint: disable=unused-argument, too-many-function-args
def setup(hass, base_config):
    """Common setup for Vera devices."""
    global VERA_CONTROLLER
    import pyvera as veraApi

    config = base_config.get(DOMAIN)
    base_url = config.get(CONF_CONTROLLER)
    VERA_CONTROLLER, _ = veraApi.init_controller(base_url)

    def stop_subscription(event):
        """Shutdown Vera subscriptions and subscription thread on exit."""
        _LOGGER.info("Shutting down subscriptions.")
        VERA_CONTROLLER.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    try:
        all_devices = VERA_CONTROLLER.get_devices()
    except RequestException:
        # There was a network related error connecting to the vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    exclude = config.get(CONF_EXCLUDE)

    lights_ids = config.get(CONF_LIGHTS)

    for device in all_devices:
        if device.device_id in exclude:
            continue
        dev_type = map_vera_device(device, lights_ids)
        if dev_type is None:
            continue
        VERA_DEVICES[dev_type].append(device)

    for component in VERA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, base_config)

    return True


def map_vera_device(vera_device, remap):
    """Map vera  classes to HA types."""
    # pylint: disable=too-many-return-statements
    import pyvera as veraApi
    if isinstance(vera_device, veraApi.VeraDimmer):
        return 'light'
    if isinstance(vera_device, veraApi.VeraBinarySensor):
        return 'binary_sensor'
    if isinstance(vera_device, veraApi.VeraSensor):
        return 'sensor'
    if isinstance(vera_device, veraApi.VeraArmableDevice):
        return 'switch'
    if isinstance(vera_device, veraApi.VeraLock):
        return 'lock'
    if isinstance(vera_device, veraApi.VeraThermostat):
        return 'climate'
    if isinstance(vera_device, veraApi.VeraCurtain):
        return 'cover'
    if isinstance(vera_device, veraApi.VeraSwitch):
        if vera_device.device_id in remap:
            return 'light'
        else:
            return 'switch'
    return None


class VeraDevice(Entity):
    """Representation of a Vera devicetity."""

    def __init__(self, vera_device, controller):
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller
        self._name = self.vera_device.name

        self.controller.register(vera_device, self._update_callback)
        self.update()

    def _update_callback(self, _device):
        self.update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = 'True' if armed else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = 'True' if tripped else 'False'

        power = self.vera_device.power
        if power:
            attr[ATTR_CURRENT_POWER_MWH] = convert(power, float, 0.0) * 1000

        attr['Vera Device Id'] = self.vera_device.vera_device_id

        return attr
