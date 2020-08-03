from .yaml_const import (CONFIG_TYPE)
from .yaml_const import (CONFIG_DEVICE_CONNECTION_PARAMS)
   
CLIMATE_IP_CONNECTIONS = []

def register_connection(conn):
    """Decorate a function to register a propery."""
    CLIMATE_IP_CONNECTIONS.append(conn)
    return conn

class Connection:
    def __init__(self, config, logger):
        self._params = {}
        self._logger = logger
        self._config = config

    @property
    def logger(self):
        return self._logger

    @property
    def config(self):
        return self._config

    def load_from_yaml(self, node, connection_base):
        """Load configuration from yaml node dictionary. Use connection base as base but DO NOT modify it.
        Return True if successful False otherwise."""
        return False

    def execute(self, template, value, device_state):
        """execute connection and return JSON object as result or None if unsuccesful."""
        return None

    def create_updated(self, yaml_node):
        """Create a copy of connection object and update this object from YAML configuration node"""
        return None

def create_connection(node, config, logger) -> Connection:
    for conn in CLIMATE_IP_CONNECTIONS:
        if CONFIG_TYPE in node:
            if conn.match_type(node[CONFIG_TYPE]):
                c = conn(config, logger)
                if c.load_from_yaml(node, None):
                    return c
    return None
