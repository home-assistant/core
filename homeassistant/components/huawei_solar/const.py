"""Constants for the Huawei Solar integration."""
from datetime import timedelta

DOMAIN = "huawei_solar"
DEFAULT_PORT = 502

DATA_MODBUS_CLIENT = "client"
DATA_DEVICE_INFO = "device_info"
DATA_EXTRA_SLAVE_IDS = "extra_slave_ids"

CONF_SLAVE_IDS = "slave_ids"

BATTERY_UPDATE_INTERVAL = timedelta(seconds=30)
INVERTER_UPDATE_INTERVAL = timedelta(seconds=30)
METER_UPDATE_INTERVAL = timedelta(seconds=15)
