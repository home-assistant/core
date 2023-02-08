"""Constants for the zcs_azzurro integration."""

DOMAIN = "zcs_azzurro_inverter"

SCHEMA_CLIENT_KEY = "client"
SCHEMA_THINGS_KEY = "thing_serial"

ENDPOINT = "https://third.zcsazzurroportal.com:19003"
AUTH_KEY = "Authorization"
AUTH_VALUE = "Zcs eHWAeEq0aYO0"
CLIENT_AUTH_KEY = "client"
CONTENT_TYPE = "application/json"
REQUEST_TIMEOUT = 5

HISTORIC_DATA_KEY = "historicData"
HISTORIC_DATA_COMMAND = "historicData"

REALTIME_DATA_KEY = "realtimeData"
REALTIME_DATA_COMMAND = "realtimeData"

DEVICES_ALARMS_KEY = "deviceAlarm"
DEVICES_ALARMS_COMMAND = "deviceAlarm"

COMMAND_KEY = "command"
PARAMS_KEY = "params"
PARAMS_THING_KEY = "thingKey"
PARAMS_REQUIRED_VALUES_KEY = "requiredValues"
PARAMS_START_KEY = "start"
PARAMS_END_KEY = "end"

RESPONSE_SUCCESS_KEY = "success"
RESPONSE_VALUES_KEY = "value"

# Values of required values
REQUIRED_VALUES_ALL = "*"
REQUIRED_VALUES_SEP = ","

# Value keys returned by Realtime Data
REALTIME_LAST_UPDATE_KEY = "lastUpdate"
REALTIME_LAST_COMM_KEY = "thingFind"
REALTIME_BATTERY_CYCLES_KEY = "batteryCycletime"
REALTIME_BATTERY_SOC_KEY = "batterySoC"
REALTIME_POWER_CHARGING_KEY = "powerCharging"
REALTIME_POWER_DISCHARGING_KEY = "powerDischarging"
REALTIME_POWER_EXPORTING_KEY = "powerExporting"
REALTIME_POWER_IMPORTING_KEY = "powerImporting"
REALTIME_POWER_CONSUMING_KEY = "powerConsuming"
REALTIME_POWER_AUTOCONSUMING_KEY = "powerAutoconsuming"
REALTIME_POWER_GENERATING_KEY = "powerGenerating"
REALTIME_ENERGY_CHARGING_KEY = "energyCharging"
REALTIME_ENERGY_DISCHARGING_KEY = "energyDischarging"
REALTIME_ENERGY_EXPORTING_KEY = "energyExporting"
REALTIME_ENERGY_IMPORTING_KEY = "energyImporting"
REALTIME_ENERGY_CONSUMING_KEY = "energyConsuming"
REALTIME_ENERGY_AUTOCONSUMING_KEY = "energyAutoconsuming"
REALTIME_ENERGY_GENERATING_KEY = "energyGenerating"
REALTIME_ENERGY_CHARGING_TOTAL_KEY = "energyChargingTotal"
REALTIME_ENERGY_DISCHARGING_TOTAL_KEY = "energyDischargingTotal"
REALTIME_ENERGY_EXPORTING_TOTAL_KEY = "energyExportingTotal"
REALTIME_ENERGY_IMPORTING_TOTAL_KEY = "energyImportingTotal"
REALTIME_ENERGY_CONSUMING_TOTAL_KEY = "energyConsumingTotal"
REALTIME_ENERGY_AUTOCONSUMING_TOTAL_KEY = "energyAutoconsumingTotal"
REALTIME_ENERGY_GENERATING_TOTAL_KEY = "energyGeneratingTotal"
