"""Constants for the Huawei Solar integration."""
from datetime import timedelta

DOMAIN = "huawei_solar"
DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 0

CONF_SLAVE_IDS = "slave_ids"

DATA_UPDATE_COORDINATORS = "update_coordinators"

UPDATE_INTERVAL = timedelta(seconds=30)
