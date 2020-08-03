import yaml
import logging
import os

from .yaml_const import (
    CONFIG_DEVICE, CONFIG_DEVICE_CONNECTION, CONFIG_DEVICE_STATUS,
    CONFIG_DEVICE_OPERATIONS, CONFIG_DEVICE_ATTRIBUTES,
    CONF_CONFIG_FILE, CONFIG_DEVICE_NAME, CONFIG_DEVICE_VALIDATE_PROPS,
    CONFIG_DEVICE_CONNECTION_PARAMS, CONFIG_DEVICE_POLL,
)

from .controller import (
    ATTR_POWER, ClimateController, register_controller
)

from .properties import (
    create_status_getter, 
    create_property
)

from .connection import (
    create_connection
)

from homeassistant.const import (
    TEMP_CELSIUS, ATTR_NAME, ATTR_TEMPERATURE,
    CONF_IP_ADDRESS, CONF_TEMPERATURE_UNIT, CONF_TOKEN,
    STATE_ON, ATTR_ENTITY_ID,
)

from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.entity_component
import voluptuous as vol

CONST_CONTROLLER_TYPE = 'yaml'
CONST_MAX_GET_STATUS_RETRIES = 4

class StreamWrapper(object):
    def __init__(self, stream, token, ip_address):
        self.stream = stream
        self.leftover = ''
        self.token = token
        self.ip_address = ip_address

    def read(self, size):
        data = self.leftover
        count = len(self.leftover)

        if count < size:
            chunk = self.stream.read(size)

            if self.token is not None:
                chunk = chunk.replace('__CLIMATE_IP_TOKEN__', self.token)
            if self.ip_address is not None:
                chunk = chunk.replace('__CLIMATE_IP_HOST__', self.ip_address)

            data += chunk
            count += len(chunk)

        self.leftover = data[size:]
        return data[:size]

@register_controller
class YamlController(ClimateController):
    def __init__(self, config, logger):
        super(YamlController, self).__init__(config, logger)
        self._logger = logger
        self._operations = {}
        self._operations_list = []
        self._properties = {}
        self._properties_list = []
        self._name = CONST_CONTROLLER_TYPE
        self._attributes = { 'controller' : self.id }
        self._state_getter = None
        self._debug = config.get('debug', False)
        self._temp_unit = TEMP_CELSIUS
        self._service_schema_map = { vol.Optional(ATTR_ENTITY_ID) : cv.comp_entity_ids }
        self._logger.setLevel(logging.INFO if self._debug else logging.ERROR)
        self._yaml = config.get(CONF_CONFIG_FILE)
        self._ip_address = config.get(CONF_IP_ADDRESS, None)
        self._token = config.get(CONF_TOKEN, None)
        self._config = config
        self._retries_count = 0
        self._last_device_state = None
        self._poll = None

    @property
    def poll(self):
        return self._poll
       
    @property
    def id(self):
        return CONST_CONTROLLER_TYPE

    def initialize(self):
        connection_params = { CONFIG_DEVICE_CONNECTION_PARAMS : { } }
        
        file = self._yaml
        if file is not None and file.find('\\') == -1 and file.find('/') == -1:
            file = os.path.join(os.path.dirname(__file__), file)
        self._logger.info("Loading configuration file: {}".format(file))

        if self._ip_address is not None:
            self._logger.info("ip_address: {}".format(self._ip_address))
        if self._token is not None:
            self._logger.info("token: {}".format(self._token))

        with open(file, 'r') as stream:
            try:
                yaml_device = yaml.load(StreamWrapper(stream, self._token, self._ip_address), Loader=yaml.FullLoader)
            except yaml.YAMLError as exc:
                if self._logger is not None:
                    self._logger.error("YAML error: {}".format(exc))
                return False
            except FileNotFoundError:
                if self._logger is not None:
                    self._logger.error("Cannot open YAML configuration file '{}'".format(self._yaml))
                return False
    
        validate_props = False
        if CONFIG_DEVICE in yaml_device:
            ac = yaml_device.get(CONFIG_DEVICE, {})
            self._poll = ac.get(CONFIG_DEVICE_POLL, None)
            validate_props = ac.get(CONFIG_DEVICE_VALIDATE_PROPS, False)
            self._logger.info("Validate properties: {} ({})".format(validate_props, ac.get(CONFIG_DEVICE_VALIDATE_PROPS, False)))
            connection_node = ac.get(CONFIG_DEVICE_CONNECTION, {})
            connection = create_connection(connection_node, self._config, self._logger)
            
            if connection is None:
                self._logger.error("Cannot create connection object!")
                return False

            self._state_getter = create_status_getter('state', ac.get(CONFIG_DEVICE_STATUS, {}), connection)
            if self._state_getter == None:
                self._logger.error("Missing 'state' configuration node")
                return False

            nodes = ac.get(CONFIG_DEVICE_OPERATIONS, {})
            for op_key in nodes.keys():
                op = create_property(op_key, nodes[op_key], connection)
                if op is not None:
                    self._operations[op.id] = op
                    self._service_schema_map[vol.Optional(op.id)] = op.config_validation_type

            nodes = ac.get(CONFIG_DEVICE_ATTRIBUTES, {})
            for key in nodes.keys():
                prop = create_property(key, nodes[key], connection)
                if prop is not None:
                    self._properties[prop.id] = prop

            self._name = ac.get(ATTR_NAME, CONST_CONTROLLER_TYPE)

        self.update_state()

        if validate_props:
            ops = {}
            device_state = self._state_getter.value
            for op in self._operations.values():
                if op.is_valid(device_state):
                    ops[op.id] = op
                else:
                    self._logger.info("Removing invalid operation '{}'".format(op.id))
                self._operations = ops
            ops = {}

        self._operations_list = [v for v in self._operations.keys() ]
        self._properties_list = [v for v in self._properties.keys() ]
        
        return ((len(self._operations) + len(self._properties)) > 0)

    @staticmethod
    def match_type(type):
        return str(type).lower() == CONST_CONTROLLER_TYPE

    @property
    def name(self):
        device_name = self.get_property(ATTR_NAME)
        return device_name if device_name is not None else self._name

    @property
    def debug(self):
        return self._debug
        
    def update_state(self):
        debug = self._debug
        self._logger.info("Updating state...")
        if self._state_getter is not None:
            self._attributes = { ATTR_NAME : self.name }
            self._logger.info("Updating getter...")
            self._state_getter.update_state(self._state_getter.value, debug)
            device_state = self._state_getter.value
            self._logger.info("Getter updated with value: {}".format(device_state))
            if device_state is None and self._retries_count > 0:
                --self._retries_count
                device_state = self._last_device_state
                self._attributes['failed_retries'] = CONST_MAX_GET_STATUS_RETRIES - --self._retries_count
            else:
                self._retries_count = CONST_MAX_GET_STATUS_RETRIES
                self._last_device_state = device_state
            if debug:
                self._attributes.update(self._state_getter.state_attributes)
            self._logger.info("Updating operations...")
            for op in self._operations.values():
                op.update_state(device_state, debug)
                self._attributes.update(op.state_attributes)
            self._logger.info("Updating properties...")
            for prop in self._properties.values():
                prop.update_state(device_state, debug)
                self._attributes.update(prop.state_attributes)

    def set_property(self, property_name, new_value):
        print("SETTING UP property {} to {}".format(property_name, new_value))
        op = self._operations.get(property_name, None)
        if op is not None:
            result = op.set_value(new_value)
            print("SETTING UP property {} to {} -> FINISHED with result {}".format(property_name, new_value, result))
            return result
        print("SETTING UP property {} to {} -> FAILED - wrong property".format(property_name, new_value))
        return False

    def get_property(self, property_name):
        if property_name in self._operations:
            return self._operations[property_name].value
        if property_name in self._properties:
            return self._properties[property_name].value
        if property_name in self._attributes:
            return self._attributes[property_name]
        return None

    @property
    def state_attributes(self):
        self._logger.info("Controller::state_attributes")
        return self._attributes

    @property
    def temperature_unit(self):
        return self._temp_unit

    @property
    def service_schema_map(self):
        return self._service_schema_map

    @property
    def operations(self):
        """ Return a list of available operations """
        return self._operations_list

    @property
    def attributes(self):
        """ Return a list of available attributes """
        return self._properties_list

