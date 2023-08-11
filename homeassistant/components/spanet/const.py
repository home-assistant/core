"""Constants for the SpaNET integration."""

DOMAIN = "spanet"

# BASE = "http://192.168.1.251:63788/"
BASE = "https://app.spanet.net.au/"

LOGIN = BASE + "api/Login/Authenticate"
GET_TEMPERATURE = BASE + "api/HomeAssistant/GetTemperature"
GET_TARGET_TEMPERATURE = BASE + "api/HomeAssistant/GetTargetTemperature"
GET_OPERATION_MODE = BASE + "api/HomeAssistant/GetOperationMode"
SET_TEMPERATURE = BASE + "api/HomeAssistant/SetTemperature"
SET_OPERATION_MODE = BASE + "api/HomeAssistant/SetOperationMode"
