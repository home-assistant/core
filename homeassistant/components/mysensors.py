"""
homeassistant.components.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MySensors component that connects to a MySensors gateway via pymysensors
API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html


New features:

New MySensors component.
Updated MySensors Sensor platform.
New MySensors Switch platform.
Multiple gateways are now supported.

Configuration.yaml:

mysensors:
  port:
    - '/dev/ttyUSB0'
    - '/dev/ttyACM1'
  debug: true
  persistence: true
  persistence_file:
    - 'path/to/.homeassistant/mysensors.json'
    - 'path/to/.homeassistant/mysensors2.json'
  version: '1.5'

sensor:
  platform: mysensors

switch:
  platform: mysensors
"""
import logging

from homeassistant.helpers import (validate_config)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELCIUS)

CONF_PORT = 'port'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = [
    'https://github.com/theolind/pymysensors/archive/'
    '2aa8f32908e8c5bb3e5c77c5851db778f8635792.zip#pymysensors==0.3']
_LOGGER = logging.getLogger(__name__)
ATTR_PORT = 'port'
ATTR_DEVICES = 'devices'
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'
ATTR_UPDATE_TYPE = 'update_type'

IS_METRIC = None
CONST = None
GATEWAYS = None
EVENT_MYSENSORS_NODE_UPDATE = 'MYSENSORS_NODE_UPDATE'


def setup(hass, config):  # noqa
    """ Setup the MySensors component. """
    # pylint:disable=no-name-in-module
    import mysensors.mysensors as mysensors

    if not validate_config(config,
                           {DOMAIN: [CONF_PORT]},
                           _LOGGER):
        return False

    version = config[DOMAIN].get(CONF_VERSION, '1.4')

    global CONST
    if version == '1.4':
        import mysensors.const_14 as const
        CONST = const
    elif version == '1.5':
        import mysensors.const_15 as const
        CONST = const
    else:
        import mysensors.const_14 as const
        CONST = const

    # Just assume celcius means that the user wants metric for now.
    # It may make more sense to make this a global config option in the future.
    global IS_METRIC
    IS_METRIC = (hass.config.temperature_unit == TEMP_CELCIUS)

    def callback_generator(port, devices):
        """Return a new callback function. Run once per gateway setup."""
        def node_update(update_type, nid):
            """Callback for node updates from the MySensors gateway."""
            _LOGGER.info('update %s: node %s', update_type, nid)

            hass.bus.fire(EVENT_MYSENSORS_NODE_UPDATE, {
                ATTR_PORT: port,
                ATTR_DEVICES: devices,
                ATTR_UPDATE_TYPE: update_type,
                ATTR_NODE_ID: nid
            })
            return
        return node_update

    def setup_gateway(port, persistence, persistence_file):
        """Return gateway after setup of the gateway."""
        devices = {}    # keep track of devices added to HA
        gateway = mysensors.SerialGateway(port,
                                          persistence=persistence,
                                          persistence_file=persistence_file,
                                          protocol_version=version)
        gateway.event_callback = callback_generator(port, devices)
        gateway.metric = IS_METRIC
        gateway.debug = config[DOMAIN].get(CONF_DEBUG, False)
        gateway.start()

        def persistence_update(event):
            """Callback to trigger update from persistence file."""
            for _ in range(2):
                for nid in gateway.sensors:
                    gateway.event_callback('persistence', nid)

        if persistence:
            hass.bus.listen_once(
                EVENT_HOMEASSISTANT_START, persistence_update)

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                             lambda event: gateway.stop())
        return gateway

    port = config[DOMAIN].get(CONF_PORT)
    persistence_file = config[DOMAIN].get(
        CONF_PERSISTENCE_FILE, hass.config.path('mysensors.pickle'))

    if isinstance(port, str):
        port = [port]
    if isinstance(persistence_file, str):
        persistence_file = [persistence_file]

    # Setup all ports from config
    global GATEWAYS
    GATEWAYS = {}
    for index, port_item in enumerate(port):
        persistence = config[DOMAIN].get(CONF_PERSISTENCE, True)
        try:
            persistence_f_item = persistence_file[index]
        except IndexError:
            _LOGGER.exception(
                'No persistence_file is set for port %s,'
                ' disabling persistence', port_item)
            persistence = False
            persistence_f_item = None
        GATEWAYS[port_item] = setup_gateway(
            port_item, persistence, persistence_f_item)

    return True


def mysensors_update(platform_type):
    """Decorator for callback function for mysensor updates."""
    def wrapper(gateway, port, devices, nid):
        """Wrapper function in the decorator."""
        if gateway.sensors[nid].sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', nid)
            return
        if nid not in devices:
            devices[nid] = {}
        node = devices[nid]
        new_devices = []
        # Get platform specific S_TYPES, V_TYPES, class and add_devices.
        (platform_s_types,
         platform_v_types,
         platform_class,
         add_devices) = platform_type(gateway, port, devices, nid)
        for child_id, child in gateway.sensors[nid].children.items():
            if child_id not in node:
                node[child_id] = {}
            for value_type, _ in child.values.items():
                if (value_type not in node[child_id] and
                        child.type in platform_s_types and
                        value_type in platform_v_types):
                    name = '{} {}.{}'.format(
                        gateway.sensors[nid].sketch_name, nid, child.id)
                    node[child_id][value_type] = platform_class(
                        port, nid, child_id, name, value_type)
                    new_devices.append(node[child_id][value_type])
                elif (child.type in platform_s_types and
                      value_type in platform_v_types):
                    node[child_id][value_type].update_sensor(
                        child.values, gateway.sensors[nid].battery_level)
        if new_devices:
            _LOGGER.info('adding new devices: %s', new_devices)
            add_devices(new_devices)
        return
    return wrapper


def event_update(update):
    """Decorator for callback function for mysensor event updates."""
    def wrapper(event):
        """Wrapper function in the decorator."""
        _LOGGER.info(
            'update %s: node %s', event.data[ATTR_UPDATE_TYPE],
            event.data[ATTR_NODE_ID])
        sensor_update = update(event)
        sensor_update(GATEWAYS[event.data[ATTR_PORT]],
                      event.data[ATTR_PORT],
                      event.data[ATTR_DEVICES],
                      event.data[ATTR_NODE_ID])
        return
    return wrapper
