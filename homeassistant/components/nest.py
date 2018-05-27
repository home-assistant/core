"""
Support for Nest devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/nest/
"""
from concurrent.futures import ThreadPoolExecutor
import logging
import socket

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_STRUCTURE, CONF_FILENAME, CONF_BINARY_SENSORS, CONF_SENSORS,
    CONF_MONITORED_CONDITIONS,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

REQUIREMENTS = ['python-nest==4.0.0']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'nest'

DATA_NEST = 'nest'

EVENT_NEST_UPDATE = 'nest_update'

NEST_CONFIG_FILE = 'nest.conf'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

ATTR_HOME_MODE = 'home_mode'
ATTR_STRUCTURE = 'structure'

SENSOR_SCHEMA = vol.Schema({
    vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(cv.ensure_list)
})

AWAY_SCHEMA = vol.Schema({
    vol.Required(ATTR_HOME_MODE): cv.string,
    vol.Optional(ATTR_STRUCTURE): vol.All(cv.ensure_list, cv.string)
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_STRUCTURE): vol.All(cv.ensure_list, cv.string),
        vol.Optional(CONF_SENSORS): SENSOR_SCHEMA,
        vol.Optional(CONF_BINARY_SENSORS): SENSOR_SCHEMA
    })
}, extra=vol.ALLOW_EXTRA)


async def async_nest_update_event_broker(hass, nest):
    """
    Fire a EVENT_NEST_UPDATE event when nest stream API received data.

    nest.update_event.wait will block the thread in most of time,
    so specific an executor to save default thread pool.
    """
    _LOGGER.debug("listening nest.update_event")
    with ThreadPoolExecutor(max_workers=1) as executor:
        while True:
            await hass.loop.run_in_executor(executor, nest.update_event.wait)
            if hass.is_running:
                _LOGGER.debug("dispatching nest data update")
                nest.update_event.clear()
                hass.bus.async_fire(EVENT_NEST_UPDATE)
            else:
                return


async def async_request_configuration(nest, hass, config):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if 'nest' in _CONFIGURING:
        _LOGGER.debug("configurator failed")
        configurator.async_notify_errors(
            _CONFIGURING['nest'], "Failed to configure, please try again.")
        return

    async def async_nest_configuration_call_back(data):
        """Run when the configuration callback is called."""
        _LOGGER.debug("configurator callback")
        pin = data.get('pin')
        await async_setup_nest(hass, nest, config, pin=pin)
        # start nest update event listener since we missed startup hook
        hass.async_add_job(async_nest_update_event_broker, hass, nest)

    _CONFIGURING['nest'] = configurator.async_request_config(
        "Nest", async_nest_configuration_call_back,
        description=('To configure Nest, click Request Authorization below, '
                     'log into your Nest account, '
                     'and then enter the resulting PIN'),
        link_name='Request Authorization',
        link_url=nest.authorize_url,
        submit_caption="Confirm",
        fields=[{'id': 'pin', 'name': 'Enter the PIN', 'type': ''}]
    )


async def async_setup_nest(hass, nest, config, pin=None):
    """Set up the Nest devices."""
    if pin is not None:
        _LOGGER.debug("pin acquired, requesting access token")
        nest.request_token(pin)

    if nest.access_token is None:
        _LOGGER.debug("no access_token, requesting configuration")
        await async_request_configuration(nest, hass, config)
        return

    if 'nest' in _CONFIGURING:
        _LOGGER.debug("configuration done")
        configurator = hass.components.configurator
        configurator.async_request_done(_CONFIGURING.pop('nest'))

    _LOGGER.debug("proceeding with setup")
    conf = config[DOMAIN]
    hass.data[DATA_NEST] = NestDevice(hass, conf, nest)

    _LOGGER.debug("proceeding with discovery -- climate")
    await discovery.async_load_platform(hass, 'climate', DOMAIN, {}, config)
    _LOGGER.debug("proceeding with discovery -- camera")
    await discovery.async_load_platform(hass, 'camera', DOMAIN, {}, config)

    _LOGGER.debug("proceeding with discovery -- sensor")
    sensor_config = conf.get(CONF_SENSORS, {})
    await discovery.async_load_platform(hass, 'sensor', DOMAIN, sensor_config,
                                        config)

    _LOGGER.debug("proceeding with discovery -- binary_sensor")
    binary_sensor_config = conf.get(CONF_BINARY_SENSORS, {})
    await discovery.async_load_platform(hass, 'binary_sensor', DOMAIN,
                                        binary_sensor_config, config)

    def start_up(event):
        """Start Nest update event listener."""
        hass.async_add_job(async_nest_update_event_broker, hass, nest)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_up)

    def shut_down(event):
        """Stop Nest update event listener."""
        if nest:
            nest.update_event.set()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shut_down)

    _LOGGER.debug("setup done")

    return True


async def async_setup(hass, config):
    """Set up Nest components."""
    import nest

    if 'nest' in _CONFIGURING:
        return

    conf = config[DOMAIN]
    client_id = conf[CONF_CLIENT_ID]
    client_secret = conf[CONF_CLIENT_SECRET]
    filename = config.get(CONF_FILENAME, NEST_CONFIG_FILE)

    access_token_cache_file = hass.config.path(filename)

    nest = nest.Nest(
        access_token_cache_file=access_token_cache_file,
        client_id=client_id, client_secret=client_secret)
    await async_setup_nest(hass, nest, config)

    def set_mode(service):
        """Set the home/away mode for a Nest structure."""
        if ATTR_STRUCTURE in service.data:
            structures = service.data[ATTR_STRUCTURE]
        else:
            structures = hass.data[DATA_NEST].local_structure

        for structure in nest.structures:
            if structure.name in structures:
                _LOGGER.info("Setting mode for %s", structure.name)
                structure.away = service.data[ATTR_HOME_MODE]
            else:
                _LOGGER.error("Invalid structure %s",
                              service.data[ATTR_STRUCTURE])

    hass.services.async_register(
        DOMAIN, 'set_mode', set_mode, schema=AWAY_SCHEMA)

    return True


class NestDevice(object):
    """Structure Nest functions for hass."""

    def __init__(self, hass, conf, nest):
        """Init Nest Devices."""
        self.hass = hass
        self.nest = nest

        if CONF_STRUCTURE not in conf:
            self.local_structure = [s.name for s in nest.structures]
        else:
            self.local_structure = conf[CONF_STRUCTURE]
        _LOGGER.debug("Structures to include: %s", self.local_structure)

    def structures(self):
        """Generate a list of structures."""
        try:
            for structure in self.nest.structures:
                if structure.name in self.local_structure:
                    yield structure
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self.local_structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def thermostats(self):
        """Generate a list of thermostats and their location."""
        try:
            for structure in self.nest.structures:
                if structure.name in self.local_structure:
                    for device in structure.thermostats:
                        yield (structure, device)
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self.local_structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def smoke_co_alarms(self):
        """Generate a list of smoke co alarms."""
        try:
            for structure in self.nest.structures:
                if structure.name in self.local_structure:
                    for device in structure.smoke_co_alarms:
                        yield (structure, device)
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self.local_structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")

    def cameras(self):
        """Generate a list of cameras."""
        try:
            for structure in self.nest.structures:
                if structure.name in self.local_structure:
                    for device in structure.cameras:
                        yield (structure, device)
                else:
                    _LOGGER.debug("Ignoring structure %s, not in %s",
                                  structure.name, self.local_structure)
        except socket.error:
            _LOGGER.error(
                "Connection error logging into the nest web service.")
