"""Constants for the HomematicIP Cloud component."""
import logging

_LOGGER = logging.getLogger('homeassistant.components.homematicip_cloud')

DOMAIN = 'homematicip_cloud'

COMPONENTS = [
    'alarm_control_panel',
    'binary_sensor',
    'climate',
    'cover',
    'light',
    'sensor',
    'switch',
]

DEFAULT_ENABLE_GROUP_SWITCHES = False
DEFAULT_ENABLE_GROUP_SEC_SENSORS = False

CONF_ACCESSPOINT = 'accesspoint'
CONF_AUTHTOKEN = 'authtoken'
CONF_ENABLE_GROUP_SWITCHES = 'enable_group_switches'
CONF_ENABLE_GROUP_SEC_SENSORS = 'enable_group_sec_sensors'

HMIPC_NAME = 'name'
HMIPC_HAPID = 'hapid'
HMIPC_AUTHTOKEN = 'authtoken'
HMIPC_PIN = 'pin'
HMIPCS_ENABLE_GROUP_SWITCHES = 'enable_group_switches'
HMIPCS_ENABLE_GROUP_SEC_SENSORS = 'enable_group_sec_sensors'
