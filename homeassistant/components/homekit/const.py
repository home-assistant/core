"""Constants used be the HomeKit component."""
# #### Misc ####
DEBOUNCE_TIMEOUT = 0.5
DOMAIN = 'homekit'
HOMEKIT_FILE = '.homekit.state'
HOMEKIT_NOTIFY_ID = 4663548

# #### Config ####
CONF_AUTO_START = 'auto_start'
CONF_ENTITY_CONFIG = 'entity_config'
CONF_FILTER = 'filter'

# #### Config Defaults ####
DEFAULT_AUTO_START = True
DEFAULT_PORT = 51827

# #### HomeKit Component Services ####
SERVICE_HOMEKIT_START = 'start'

# #### String Constants ####
BRIDGE_MODEL = 'Bridge'
BRIDGE_NAME = 'Home Assistant Bridge'
BRIDGE_SERIAL_NUMBER = 'homekit.bridge'
MANUFACTURER = 'Home Assistant'

# #### Services ####
SERV_ACCESSORY_INFO = 'AccessoryInformation'
SERV_AIR_QUALITY_SENSOR = 'AirQualitySensor'
SERV_CARBON_DIOXIDE_SENSOR = 'CarbonDioxideSensor'
SERV_CARBON_MONOXIDE_SENSOR = 'CarbonMonoxideSensor'
SERV_CONTACT_SENSOR = 'ContactSensor'
SERV_FANV2 = 'Fanv2'
SERV_GARAGE_DOOR_OPENER = 'GarageDoorOpener'
SERV_HUMIDITY_SENSOR = 'HumiditySensor'
SERV_LEAK_SENSOR = 'LeakSensor'
SERV_LIGHT_SENSOR = 'LightSensor'
SERV_LIGHTBULB = 'Lightbulb'
SERV_LOCK = 'LockMechanism'
SERV_MOTION_SENSOR = 'MotionSensor'
SERV_OCCUPANCY_SENSOR = 'OccupancySensor'
SERV_SECURITY_SYSTEM = 'SecuritySystem'
SERV_SMOKE_SENSOR = 'SmokeSensor'
SERV_SWITCH = 'Switch'
SERV_TEMPERATURE_SENSOR = 'TemperatureSensor'
SERV_THERMOSTAT = 'Thermostat'
SERV_WINDOW_COVERING = 'WindowCovering'

# #### Characteristics ####
CHAR_ACTIVE = 'Active'
CHAR_AIR_PARTICULATE_DENSITY = 'AirParticulateDensity'
CHAR_AIR_QUALITY = 'AirQuality'
CHAR_BRIGHTNESS = 'Brightness'
CHAR_CARBON_DIOXIDE_DETECTED = 'CarbonDioxideDetected'
CHAR_CARBON_DIOXIDE_LEVEL = 'CarbonDioxideLevel'
CHAR_CARBON_DIOXIDE_PEAK_LEVEL = 'CarbonDioxidePeakLevel'
CHAR_CARBON_MONOXIDE_DETECTED = 'CarbonMonoxideDetected'
CHAR_COLOR_TEMPERATURE = 'ColorTemperature'
CHAR_CONTACT_SENSOR_STATE = 'ContactSensorState'
CHAR_COOLING_THRESHOLD_TEMPERATURE = 'CoolingThresholdTemperature'
CHAR_CURRENT_AMBIENT_LIGHT_LEVEL = 'CurrentAmbientLightLevel'
CHAR_CURRENT_DOOR_STATE = 'CurrentDoorState'
CHAR_CURRENT_HEATING_COOLING = 'CurrentHeatingCoolingState'
CHAR_CURRENT_POSITION = 'CurrentPosition'
CHAR_CURRENT_HUMIDITY = 'CurrentRelativeHumidity'
CHAR_CURRENT_SECURITY_STATE = 'SecuritySystemCurrentState'
CHAR_CURRENT_TEMPERATURE = 'CurrentTemperature'
CHAR_FIRMWARE_REVISION = 'FirmwareRevision'
CHAR_HEATING_THRESHOLD_TEMPERATURE = 'HeatingThresholdTemperature'
CHAR_HUE = 'Hue'
CHAR_LEAK_DETECTED = 'LeakDetected'
CHAR_LOCK_CURRENT_STATE = 'LockCurrentState'
CHAR_LOCK_TARGET_STATE = 'LockTargetState'
CHAR_LINK_QUALITY = 'LinkQuality'
CHAR_MANUFACTURER = 'Manufacturer'
CHAR_MODEL = 'Model'
CHAR_MOTION_DETECTED = 'MotionDetected'
CHAR_NAME = 'Name'
CHAR_OCCUPANCY_DETECTED = 'OccupancyDetected'
CHAR_ON = 'On'
CHAR_POSITION_STATE = 'PositionState'
CHAR_ROTATION_DIRECTION = 'RotationDirection'
CHAR_SATURATION = 'Saturation'
CHAR_SERIAL_NUMBER = 'SerialNumber'
CHAR_SMOKE_DETECTED = 'SmokeDetected'
CHAR_SWING_MODE = 'SwingMode'
CHAR_TARGET_DOOR_STATE = 'TargetDoorState'
CHAR_TARGET_HEATING_COOLING = 'TargetHeatingCoolingState'
CHAR_TARGET_POSITION = 'TargetPosition'
CHAR_TARGET_SECURITY_STATE = 'SecuritySystemTargetState'
CHAR_TARGET_TEMPERATURE = 'TargetTemperature'
CHAR_TEMP_DISPLAY_UNITS = 'TemperatureDisplayUnits'

# #### Properties ####
PROP_MAX_VALUE = 'maxValue'
PROP_MIN_VALUE = 'minValue'
PROP_CELSIUS = {'minValue': -273, 'maxValue': 999}

# #### Device Classes ####
DEVICE_CLASS_CO2 = 'co2'
DEVICE_CLASS_DOOR = 'door'
DEVICE_CLASS_GARAGE_DOOR = 'garage_door'
DEVICE_CLASS_GAS = 'gas'
DEVICE_CLASS_MOISTURE = 'moisture'
DEVICE_CLASS_MOTION = 'motion'
DEVICE_CLASS_OCCUPANCY = 'occupancy'
DEVICE_CLASS_OPENING = 'opening'
DEVICE_CLASS_PM25 = 'pm25'
DEVICE_CLASS_SMOKE = 'smoke'
DEVICE_CLASS_WINDOW = 'window'
