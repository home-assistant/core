"""Constants used be the HomeKit component."""
# #### Misc ####
DEBOUNCE_TIMEOUT = 0.5
DEVICE_PRECISION_LEEWAY = 6
DOMAIN = "homekit"
HOMEKIT_FILE = ".homekit.state"
HOMEKIT_NOTIFY_ID = 4663548


# #### Attributes ####
ATTR_DISPLAY_NAME = "display_name"
ATTR_VALUE = "value"

# #### Config ####
CONF_ADVERTISE_IP = "advertise_ip"
CONF_AUTO_START = "auto_start"
CONF_ENTITY_CONFIG = "entity_config"
CONF_FEATURE = "feature"
CONF_FEATURE_LIST = "feature_list"
CONF_FILTER = "filter"
CONF_LINKED_BATTERY_SENSOR = "linked_battery_sensor"
CONF_LOW_BATTERY_THRESHOLD = "low_battery_threshold"
CONF_SAFE_MODE = "safe_mode"

# #### Config Defaults ####
DEFAULT_AUTO_START = True
DEFAULT_LOW_BATTERY_THRESHOLD = 20
DEFAULT_PORT = 51827
DEFAULT_SAFE_MODE = False

# #### Features ####
FEATURE_ON_OFF = "on_off"
FEATURE_PLAY_PAUSE = "play_pause"
FEATURE_PLAY_STOP = "play_stop"
FEATURE_TOGGLE_MUTE = "toggle_mute"

# #### HomeKit Component Event ####
EVENT_HOMEKIT_CHANGED = "homekit_state_change"

# #### HomeKit Component Services ####
SERVICE_HOMEKIT_START = "start"
SERVICE_HOMEKIT_RESET_ACCESSORY = "reset_accessory"

# #### String Constants ####
BRIDGE_MODEL = "Bridge"
BRIDGE_NAME = "Home Assistant Bridge"
BRIDGE_SERIAL_NUMBER = "homekit.bridge"
MANUFACTURER = "Home Assistant"

# #### Switch Types ####
TYPE_FAUCET = "faucet"
TYPE_OUTLET = "outlet"
TYPE_SHOWER = "shower"
TYPE_SPRINKLER = "sprinkler"
TYPE_SWITCH = "switch"
TYPE_VALVE = "valve"

# #### Services ####
SERV_ACCESSORY_INFO = "AccessoryInformation"
SERV_AIR_QUALITY_SENSOR = "AirQualitySensor"
SERV_BATTERY_SERVICE = "BatteryService"
SERV_CARBON_DIOXIDE_SENSOR = "CarbonDioxideSensor"
SERV_CARBON_MONOXIDE_SENSOR = "CarbonMonoxideSensor"
SERV_CONTACT_SENSOR = "ContactSensor"
SERV_FANV2 = "Fanv2"
SERV_GARAGE_DOOR_OPENER = "GarageDoorOpener"
SERV_HUMIDITY_SENSOR = "HumiditySensor"
SERV_INPUT_SOURCE = "InputSource"
SERV_LEAK_SENSOR = "LeakSensor"
SERV_LIGHT_SENSOR = "LightSensor"
SERV_LIGHTBULB = "Lightbulb"
SERV_LOCK = "LockMechanism"
SERV_MOTION_SENSOR = "MotionSensor"
SERV_OCCUPANCY_SENSOR = "OccupancySensor"
SERV_OUTLET = "Outlet"
SERV_SECURITY_SYSTEM = "SecuritySystem"
SERV_SMOKE_SENSOR = "SmokeSensor"
SERV_SWITCH = "Switch"
SERV_TELEVISION = "Television"
SERV_TELEVISION_SPEAKER = "TelevisionSpeaker"
SERV_TEMPERATURE_SENSOR = "TemperatureSensor"
SERV_THERMOSTAT = "Thermostat"
SERV_VALVE = "Valve"
SERV_WINDOW_COVERING = "WindowCovering"

# #### Characteristics ####
CHAR_ACTIVE = "Active"
CHAR_ACTIVE_IDENTIFIER = "ActiveIdentifier"
CHAR_AIR_PARTICULATE_DENSITY = "AirParticulateDensity"
CHAR_AIR_QUALITY = "AirQuality"
CHAR_BATTERY_LEVEL = "BatteryLevel"
CHAR_BRIGHTNESS = "Brightness"
CHAR_CARBON_DIOXIDE_DETECTED = "CarbonDioxideDetected"
CHAR_CARBON_DIOXIDE_LEVEL = "CarbonDioxideLevel"
CHAR_CARBON_DIOXIDE_PEAK_LEVEL = "CarbonDioxidePeakLevel"
CHAR_CARBON_MONOXIDE_DETECTED = "CarbonMonoxideDetected"
CHAR_CARBON_MONOXIDE_LEVEL = "CarbonMonoxideLevel"
CHAR_CARBON_MONOXIDE_PEAK_LEVEL = "CarbonMonoxidePeakLevel"
CHAR_CHARGING_STATE = "ChargingState"
CHAR_COLOR_TEMPERATURE = "ColorTemperature"
CHAR_CONFIGURED_NAME = "ConfiguredName"
CHAR_CONTACT_SENSOR_STATE = "ContactSensorState"
CHAR_COOLING_THRESHOLD_TEMPERATURE = "CoolingThresholdTemperature"
CHAR_CURRENT_AMBIENT_LIGHT_LEVEL = "CurrentAmbientLightLevel"
CHAR_CURRENT_DOOR_STATE = "CurrentDoorState"
CHAR_CURRENT_HEATING_COOLING = "CurrentHeatingCoolingState"
CHAR_CURRENT_POSITION = "CurrentPosition"
CHAR_CURRENT_HUMIDITY = "CurrentRelativeHumidity"
CHAR_CURRENT_SECURITY_STATE = "SecuritySystemCurrentState"
CHAR_CURRENT_TEMPERATURE = "CurrentTemperature"
CHAR_CURRENT_TILT_ANGLE = "CurrentHorizontalTiltAngle"
CHAR_CURRENT_VISIBILITY_STATE = "CurrentVisibilityState"
CHAR_FIRMWARE_REVISION = "FirmwareRevision"
CHAR_HEATING_THRESHOLD_TEMPERATURE = "HeatingThresholdTemperature"
CHAR_HUE = "Hue"
CHAR_IDENTIFIER = "Identifier"
CHAR_IN_USE = "InUse"
CHAR_INPUT_SOURCE_TYPE = "InputSourceType"
CHAR_IS_CONFIGURED = "IsConfigured"
CHAR_LEAK_DETECTED = "LeakDetected"
CHAR_LOCK_CURRENT_STATE = "LockCurrentState"
CHAR_LOCK_TARGET_STATE = "LockTargetState"
CHAR_LINK_QUALITY = "LinkQuality"
CHAR_MANUFACTURER = "Manufacturer"
CHAR_MODEL = "Model"
CHAR_MOTION_DETECTED = "MotionDetected"
CHAR_MUTE = "Mute"
CHAR_NAME = "Name"
CHAR_OCCUPANCY_DETECTED = "OccupancyDetected"
CHAR_ON = "On"
CHAR_OUTLET_IN_USE = "OutletInUse"
CHAR_POSITION_STATE = "PositionState"
CHAR_REMOTE_KEY = "RemoteKey"
CHAR_ROTATION_DIRECTION = "RotationDirection"
CHAR_ROTATION_SPEED = "RotationSpeed"
CHAR_SATURATION = "Saturation"
CHAR_SERIAL_NUMBER = "SerialNumber"
CHAR_SLEEP_DISCOVER_MODE = "SleepDiscoveryMode"
CHAR_SMOKE_DETECTED = "SmokeDetected"
CHAR_STATUS_LOW_BATTERY = "StatusLowBattery"
CHAR_SWING_MODE = "SwingMode"
CHAR_TARGET_DOOR_STATE = "TargetDoorState"
CHAR_TARGET_HEATING_COOLING = "TargetHeatingCoolingState"
CHAR_TARGET_POSITION = "TargetPosition"
CHAR_TARGET_HUMIDITY = "TargetRelativeHumidity"
CHAR_TARGET_SECURITY_STATE = "SecuritySystemTargetState"
CHAR_TARGET_TEMPERATURE = "TargetTemperature"
CHAR_TARGET_TILT_ANGLE = "TargetHorizontalTiltAngle"
CHAR_TEMP_DISPLAY_UNITS = "TemperatureDisplayUnits"
CHAR_VALVE_TYPE = "ValveType"
CHAR_VOLUME = "Volume"
CHAR_VOLUME_SELECTOR = "VolumeSelector"
CHAR_VOLUME_CONTROL_TYPE = "VolumeControlType"


# #### Properties ####
PROP_MAX_VALUE = "maxValue"
PROP_MIN_VALUE = "minValue"
PROP_MIN_STEP = "minStep"
PROP_CELSIUS = {"minValue": -273, "maxValue": 999}

# #### Device Classes ####
DEVICE_CLASS_CO = "co"
DEVICE_CLASS_CO2 = "co2"
DEVICE_CLASS_DOOR = "door"
DEVICE_CLASS_GARAGE_DOOR = "garage_door"
DEVICE_CLASS_GAS = "gas"
DEVICE_CLASS_MOISTURE = "moisture"
DEVICE_CLASS_MOTION = "motion"
DEVICE_CLASS_OCCUPANCY = "occupancy"
DEVICE_CLASS_OPENING = "opening"
DEVICE_CLASS_PM25 = "pm25"
DEVICE_CLASS_SMOKE = "smoke"
DEVICE_CLASS_WINDOW = "window"

# #### Thresholds ####
THRESHOLD_CO = 25
THRESHOLD_CO2 = 1000

# #### Default values ####
DEFAULT_MIN_TEMP_WATER_HEATER = 40  # °C
DEFAULT_MAX_TEMP_WATER_HEATER = 60  # °C
