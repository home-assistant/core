"""
homeassistant.components.mysensors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
MySensors component that connects to a MySensors gateway via pymysensors
API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.mysensors.html
"""
import logging

from homeassistant.helpers import (validate_config)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    TEMP_CELCIUS)

CONF_PORT = 'port'
CONF_DEBUG = 'debug'
CONF_PERSISTENCE = 'persistence'
CONF_PERSISTENCE_FILE = 'persistence_file'
CONF_VERSION = 'version'

DOMAIN = 'mysensors'
DEPENDENCIES = []
REQUIREMENTS = ['file:///home/martin/Dev/pymysensors-fifo_queue.zip'
                '#pymysensors==0.3']
_LOGGER = logging.getLogger(__name__)
ATTR_NODE_ID = 'node_id'
ATTR_CHILD_ID = 'child_id'

PLATFORM_FORMAT = '{}.{}'
IS_METRIC = None
DEVICES = None
GATEWAY = None

EVENT_MYSENSORS_NODE_UPDATE = 'MYSENSORS_NODE_UPDATE'
UPDATE_TYPE = 'update_type'
NODE_ID = 'nid'

CONST = None


def setup(hass, config):
    """ Setup the MySensors component. """

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
        _LOGGER.info('CONST = %s, 1.4', const)
    elif version == '1.5':
        import mysensors.const_15 as const
        CONST = const
        _LOGGER.info('CONST = %s, 1.5', const)
    else:
        import mysensors.const_14 as const
        CONST = const
        _LOGGER.info('CONST = %s, 1.4 default', const)

    global IS_METRIC
    # Just assume celcius means that the user wants metric for now.
    # It may make more sense to make this a global config option in the future.
    IS_METRIC = (hass.config.temperature_unit == TEMP_CELCIUS)
    global DEVICES
    DEVICES = {}    # keep track of devices added to HA

    def node_update(update_type, nid):
        """ Callback for node updates from the MySensors gateway. """
        _LOGGER.info('update %s: node %s', update_type, nid)

        hass.bus.fire(EVENT_MYSENSORS_NODE_UPDATE, {
            UPDATE_TYPE: update_type,
            NODE_ID: nid
        })

    port = config[DOMAIN].get(CONF_PORT)

    persistence = config[DOMAIN].get(CONF_PERSISTENCE, True)
    persistence_file = config[DOMAIN].get(
        CONF_PERSISTENCE_FILE, hass.config.path('mysensors.pickle'))

    global GATEWAY
    GATEWAY = mysensors.SerialGateway(port, node_update,
                                      persistence=persistence,
                                      persistence_file=persistence_file,
                                      protocol_version=version)
    GATEWAY.metric = IS_METRIC
    GATEWAY.debug = config[DOMAIN].get(CONF_DEBUG, False)
    GATEWAY.start()

    if persistence:
        for nid in GATEWAY.sensors:
            node_update('node_update', nid)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP,
                         lambda event: GATEWAY.stop())

    return True


def mysensors_update(platform_type):
    """
    Decorator for callback function for sensor updates from the MySensors
    component.
    """
    def wrapper(gateway, devices, nid):
        """Wrapper function in the decorator."""
        sensor = gateway.sensors[nid]
        if sensor.sketch_name is None:
            _LOGGER.info('No sketch_name: node %s', nid)
            return
        if nid not in devices:
            devices[nid] = {}
        node = devices[nid]
        new_devices = []
        platform_def = platform_type(gateway, devices, nid)
        platform_object = platform_def['platform_class']
        platform_v_types = platform_def['types_to_handle']
        add_devices = platform_def['add_devices']
        for child_id, child in sensor.children.items():
            if child_id not in node:
                node[child_id] = {}
            for value_type, value in child.values.items():
                if value_type not in node[child_id]:
                    name = '{} {}.{}'.format(
                        sensor.sketch_name, nid, child.id)
                    if value_type in platform_v_types:
                        node[child_id][value_type] = \
                            platform_object(
                                gateway, nid, child_id, name, value_type)
                        new_devices.append(node[child_id][value_type])
                else:
                    node[child_id][value_type].update_sensor(
                        value, sensor.battery_level)
        _LOGGER.info('sensor_update: %s', new_devices)
        if new_devices:
            _LOGGER.info('adding new devices: %s', new_devices)
            add_devices(new_devices)
        return
    return wrapper
