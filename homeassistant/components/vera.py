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
from homeassistant.util import convert, slugify
from homeassistant.helpers import discovery
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    EVENT_HOMEASSISTANT_STOP, CONF_LIGHTS, CONF_EXCLUDE)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyvera==0.2.45']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vera'

VERA_CONTROLLER = 'vera_controller'

CONF_CONTROLLER = 'vera_controller_url'

VERA_ID_FORMAT = '{}_{}'

ATTR_CURRENT_POWER_W = "current_power_w"
ATTR_CURRENT_ENERGY_KWH = "current_energy_kwh"

VERA_DEVICES = 'vera_devices'
VERA_SCENES = 'vera_scenes'

VERA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CONTROLLER): cv.url,
        vol.Optional(CONF_EXCLUDE, default=[]): VERA_ID_LIST_SCHEMA,
        vol.Optional(CONF_LIGHTS, default=[]): VERA_ID_LIST_SCHEMA
    }),
}, extra=vol.ALLOW_EXTRA)

VERA_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch',
    'lock', 'climate', 'cover', 'scene'
]


def setup(hass, base_config):
    """Set up for Vera devices."""
    import pyvera as veraApi

    def stop_subscription(event):
        """Shutdown Vera subscriptions and subscription thread on exit."""
        _LOGGER.info("Shutting down subscriptions")
        hass.data[VERA_CONTROLLER].stop()

    config = base_config.get(DOMAIN)

    # Get Vera specific configuration.
    base_url = config.get(CONF_CONTROLLER)
    light_ids = config.get(CONF_LIGHTS)
    exclude_ids = config.get(CONF_EXCLUDE)

    # Initialize the Vera controller.
    controller, _ = veraApi.init_controller(base_url)
    hass.data[VERA_CONTROLLER] = controller
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    try:
        all_devices = controller.get_devices()

        all_scenes = controller.get_scenes()
    except RequestException:
        # There was a network related error connecting to the Vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    # Exclude devices unwanted by user.
    devices = [device for device in all_devices
               if device.device_id not in exclude_ids]

    vera_devices = defaultdict(list)
    for device in devices:
        device_type = map_vera_device(device, light_ids)
        if device_type is None:
            continue

        vera_devices[device_type].append(device)
    hass.data[VERA_DEVICES] = vera_devices

    vera_scenes = []
    for scene in all_scenes:
        vera_scenes.append(scene)
    hass.data[VERA_SCENES] = vera_scenes

    for component in VERA_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, base_config)

    return True


def map_vera_device(vera_device, remap):
    """Map vera classes to Home Assistant types."""
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
    if isinstance(vera_device, veraApi.VeraSceneController):
        return 'sensor'
    if isinstance(vera_device, veraApi.VeraSwitch):
        if vera_device.device_id in remap:
            return 'light'
        return 'switch'
    return None


class VeraDevice(Entity):
    """Representation of a Vera device entity."""

    def __init__(self, vera_device, controller):
        """Initialize the device."""
        self.vera_device = vera_device
        self.controller = controller

        self._name = self.vera_device.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_device.name), vera_device.device_id)

        self.controller.register(vera_device, self._update_callback)

    def _update_callback(self, _device):
        """Update the state."""
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Get polling requirement from vera device."""
        return self.vera_device.should_poll

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level

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
            attr[ATTR_CURRENT_POWER_W] = convert(power, float, 0.0)

        energy = self.vera_device.energy
        if energy:
            attr[ATTR_CURRENT_ENERGY_KWH] = convert(energy, float, 0.0)

        attr['Vera Device Id'] = self.vera_device.vera_device_id

        return attr

    @property
    def unique_id(self) -> str:
        """Return a unique ID.

        The Vera assigns a unique and immutable ID number to each device.
        """
        return str(self.vera_device.vera_device_id)
