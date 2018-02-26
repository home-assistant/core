"""Constants used be the HomeKit component."""
MANUFACTURER = 'HomeAssistant'

# Service: AccessoryInfomation
SERV_ACCESSORY_INFO = 'AccessoryInformation'
CHAR_MODEL = 'Model'
CHAR_MANUFACTURER = 'Manufacturer'
CHAR_SERIAL_NUMBER = 'SerialNumber'

# Service: TemperatureSensor
SERV_TEMPERATURE_SENSOR = 'TemperatureSensor'
CHAR_CURRENT_TEMPERATURE = 'CurrentTemperature'

# Service: WindowCovering
SERV_WINDOW_COVERING = 'WindowCovering'
CHAR_CURRENT_POSITION = 'CurrentPosition'
CHAR_TARGET_POSITION = 'TargetPosition'
CHAR_POSITION_STATE = 'PositionState'

# Properties
PROP_CELSIUS = {'minValue': -273, 'maxValue': 999}
