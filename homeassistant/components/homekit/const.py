"""Constants used be the HomeKit component."""
# #### MISC ####
DOMAIN = 'homekit'
HOMEKIT_FILE = '.homekit.state'
HOMEKIT_NOTIFY_ID = 4663548

# #### CONFIG ####
CONF_AUTO_START = 'auto_start'
CONF_ENTITY_CONFIG = 'entity_config'
CONF_FILTER = 'filter'

# #### CONFIG DEFAULTS ####
DEFAULT_AUTO_START = True
DEFAULT_PORT = 51827

# #### HOMEKIT COMPONENT SERVICES ####
SERVICE_HOMEKIT_START = 'start'

# #### STRING CONSTANTS ####
ACCESSORY_MODEL = 'homekit.accessory'
ACCESSORY_NAME = 'Home Accessory'
BRIDGE_MODEL = 'homekit.bridge'
BRIDGE_NAME = 'Home Assistant'
MANUFACTURER = 'HomeAssistant'

# #### Categories ####
CATEGORY_ALARM_SYSTEM = 'ALARM_SYSTEM'
CATEGORY_LIGHT = 'LIGHTBULB'
CATEGORY_SENSOR = 'SENSOR'
CATEGORY_SWITCH = 'SWITCH'
CATEGORY_THERMOSTAT = 'THERMOSTAT'
CATEGORY_WINDOW_COVERING = 'WINDOW_COVERING'


# #### Services ####
SERV_ACCESSORY_INFO = 'AccessoryInformation'
SERV_HUMIDITY_SENSOR = 'HumiditySensor'
# CurrentRelativeHumidity | StatusActive, StatusFault, StatusTampered,
# StatusLowBattery, Name
SERV_LIGHTBULB = 'Lightbulb'  # On | Brightness, Hue, Saturation, Name
SERV_SECURITY_SYSTEM = 'SecuritySystem'
SERV_SWITCH = 'Switch'
SERV_TEMPERATURE_SENSOR = 'TemperatureSensor'
SERV_THERMOSTAT = 'Thermostat'
SERV_WINDOW_COVERING = 'WindowCovering'


# #### Characteristics ####
CHAR_BRIGHTNESS = 'Brightness'  # Int | [0, 100]
CHAR_COLOR_TEMPERATURE = 'ColorTemperature'
CHAR_COOLING_THRESHOLD_TEMPERATURE = 'CoolingThresholdTemperature'
CHAR_CURRENT_HEATING_COOLING = 'CurrentHeatingCoolingState'
CHAR_CURRENT_POSITION = 'CurrentPosition'
CHAR_CURRENT_HUMIDITY = 'CurrentRelativeHumidity'  # percent
CHAR_CURRENT_SECURITY_STATE = 'SecuritySystemCurrentState'
CHAR_CURRENT_TEMPERATURE = 'CurrentTemperature'
CHAR_HEATING_THRESHOLD_TEMPERATURE = 'HeatingThresholdTemperature'
CHAR_HUE = 'Hue'  # arcdegress | [0, 360]
CHAR_MANUFACTURER = 'Manufacturer'
CHAR_MODEL = 'Model'
CHAR_NAME = 'Name'
CHAR_ON = 'On'  # boolean
CHAR_POSITION_STATE = 'PositionState'
CHAR_SATURATION = 'Saturation'  # percent
CHAR_SERIAL_NUMBER = 'SerialNumber'
CHAR_TARGET_HEATING_COOLING = 'TargetHeatingCoolingState'
CHAR_TARGET_POSITION = 'TargetPosition'
CHAR_TARGET_SECURITY_STATE = 'SecuritySystemTargetState'
CHAR_TARGET_TEMPERATURE = 'TargetTemperature'
CHAR_TEMP_DISPLAY_UNITS = 'TemperatureDisplayUnits'

# #### Properties ####
PROP_CELSIUS = {'minValue': -273, 'maxValue': 999}
