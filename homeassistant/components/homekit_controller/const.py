"""Constants for the homekit_controller component."""
DOMAIN = 'homekit_controller'

KNOWN_DEVICES = "{}-devices".format(DOMAIN)
CONTROLLER = "{}-controller".format(DOMAIN)
ENTITY_MAP = '{}-entity-map'.format(DOMAIN)

HOMEKIT_DIR = '.homekit'
PAIRING_FILE = 'pairing.json'

# Mapping from Homekit type to component.
HOMEKIT_ACCESSORY_DISPATCH = {
    'lightbulb': 'light',
    'outlet': 'switch',
    'switch': 'switch',
    'thermostat': 'climate',
    'security-system': 'alarm_control_panel',
    'garage-door-opener': 'cover',
    'window': 'cover',
    'window-covering': 'cover',
    'lock-mechanism': 'lock',
    'motion': 'binary_sensor',
    'humidity': 'sensor',
    'light': 'sensor',
    'temperature': 'sensor'
}
