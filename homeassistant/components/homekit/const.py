"""Constants used be the HomeKit component."""
MANUFACTURER = 'HomeAssistant'

# Services
SERV_ACCESSORY_INFO = 'AccessoryInformation'
SERV_BRIDGING_STATE = 'BridgingState'
SERV_TEMPERATURE_SENSOR = 'TemperatureSensor'
SERV_WINDOW_COVERING = 'WindowCovering'

# Characteristics
CHAR_ACC_IDENTIFIER = 'AccessoryIdentifier'
CHAR_CATEGORY = 'Category'
CHAR_CURRENT_POSITION = 'CurrentPosition'
CHAR_CURRENT_TEMPERATURE = 'CurrentTemperature'
CHAR_LINK_QUALITY = 'LinkQuality'
CHAR_MANUFACTURER = 'Manufacturer'
CHAR_MODEL = 'Model'
CHAR_POSITION_STATE = 'PositionState'
CHAR_REACHABLE = 'Reachable'
CHAR_SERIAL_NUMBER = 'SerialNumber'
CHAR_TARGET_POSITION = 'TargetPosition'

# Properties
PROP_CELSIUS = {'minValue': -273, 'maxValue': 999}
