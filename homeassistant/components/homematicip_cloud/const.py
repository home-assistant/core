"""Constants for the HomematicIP Cloud component."""
import logging

_LOGGER = logging.getLogger('homeassistant.components.homematicip_cloud')

DOMAIN = 'homematicip_cloud'

COMPONENTS = [
    'alarm_control_panel',
    'binary_sensor',
    'climate',
    'light',
    'sensor',
    'switch',
]

CONF_ACCESSPOINT = 'accesspoint'
CONF_AUTHTOKEN = 'authtoken'

HMIPC_NAME = 'name'
HMIPC_HAPID = 'hapid'
HMIPC_AUTHTOKEN = 'authtoken'
HMIPC_PIN = 'pin'
