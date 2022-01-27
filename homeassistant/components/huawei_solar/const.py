"""Constants for the Huawei Solar integration."""
from datetime import timedelta

DOMAIN = "huawei_solar"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 0

DATA_MODBUS_CLIENT = "client"
DATA_SLAVE_IDS = "slave_ids"
DATA_DEVICE_INFOS = "device_infos"
DATA_UPDATE_COORDINATORS = "update_coordinators"

CONF_SLAVE_IDS = "slave_ids"

IDENTIFIER_SLAVE_ID = "slave_id"
IDENTIFIER_DEVICE_TYPE = "device_type"

DEVICE_TYPE_INVERTER = "inverter"
DEVICE_TYPE_ENERGY_STORAGE = "energy_storage"
DEVICE_TYPE_SINGLE_PHASE_POWER_METER = "single_phase_power_meter"
DEVICE_TYPE_THREE_PHASE_POWER_METER = "three_phase_power_meter"


BATTERY_UPDATE_INTERVAL = timedelta(seconds=30)
INVERTER_UPDATE_INTERVAL = timedelta(seconds=30)
METER_UPDATE_INTERVAL = timedelta(seconds=15)
