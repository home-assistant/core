"""Constants for hello auth integration."""

import logging

DEFAULT_ACCESS = ["https://www.googleapis.com/auth/youtube.readonly"]
DOMAIN = "hinen"
MANUFACTURER = "hinen"
CHANNEL_CREATION_HELP_URL = "https://support.google.com/youtube/answer/1646861"

CONF_DEVICES = "devices"
COORDINATOR = "coordinator"
AUTH = "auth"
HOST = "host"

LOGGER = logging.getLogger(__package__)

ATTR_REGION_CODE = "region_code"
ATTR_CLIENT_SECRET = "client_secret"
ATTR_STATUS = "status"
ATTR_WORD_MODE = "vpp_work_mode"
ATTR_ALERT_STATUS = "alert_status"
ATTR_DEVICE_NAME = "device_name"

REGION_CODE = "regionCode"
CLIENT_SECRET = "clientSecret"
# Work mode constants
WORK_MODE = "VPPWorkMode"
WORK_MODE_NONE = 0
WORK_MODE_SELF_CONSUMPTION = 1
WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY = 2
WORK_MODE_SPECIFIED_POWER_CHARGE = 3
WORK_MODE_SPECIFIED_POWER_DISCHARGE = 4
WORK_MODE_BATTERY_IDLE = 5
WORK_MODE_CHARGE_DISCHARGE_TIME = 6

WORK_MODE_OPTIONS = {
    WORK_MODE_NONE: "none",
    WORK_MODE_SELF_CONSUMPTION: "Self-use",
    WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY: "Self-use(Generate only)",
    WORK_MODE_SPECIFIED_POWER_CHARGE: "Specified power charging",
    WORK_MODE_SPECIFIED_POWER_DISCHARGE: "Specified power discharge",
    WORK_MODE_BATTERY_IDLE: "Battery idle",
    WORK_MODE_CHARGE_DISCHARGE_TIME: "Charging and discharge time period",
}

LOAD_FIRST_STOP_SOC = "load_first_stop_soc"
CHARGE_STOP_SOC = "charge_stop_soc"
GRID_FIRST_STOP_SOC = "grid_first_stop_soc"
CHARGE_POWER_SET = "charge_power_set"
DISCHARGE_POWER_SET = "discharge_power_set"

PROPERTIES = {
    LOAD_FIRST_STOP_SOC: "LoadFirstStopSOC",
    CHARGE_STOP_SOC: "ChargeStopSOC",
    GRID_FIRST_STOP_SOC: "GridFirstStopSOC",
    CHARGE_POWER_SET: "ChargePowerSet",
    DISCHARGE_POWER_SET: "DischargePowerSet",
}

ATTR_AUTH_LANGUAGE = "page_language"
ATTR_REDIRECTION_URL = "redirection_url"
SUPPORTED_LANGUAGES = [("en_US", "English"), ("zh_CN", "Chinese")]

CLIENT_ID = "W4lHyHTK"
