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
ATTR_ALERT_STATUS = "alert_status"
ATTR_DEVICE_NAME = "device_name"

REGION_CODE = "regionCode"
CLIENT_SECRET = "clientSecret"
# Work mode constants
VPP_WORK_MODE_NONE = 0
VPP_WORK_MODE_SELF_CONSUMPTION = 1
VPP_WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY = 2
VPP_WORK_MODE_SPECIFIED_POWER_CHARGE = 3
VPP_WORK_MODE_SPECIFIED_POWER_DISCHARGE = 4
VPP_WORK_MODE_BATTERY_IDLE = 5
VPP_WORK_MODE_CHARGE_DISCHARGE_TIME = 6

VPP_WORK_MODE_OPTIONS = {
    VPP_WORK_MODE_NONE: "none",
    VPP_WORK_MODE_SELF_CONSUMPTION: "Self-use",
    VPP_WORK_MODE_SELF_CONSUMPTION_CHARGE_ONLY: "Self-use(Generate only)",
    VPP_WORK_MODE_SPECIFIED_POWER_CHARGE: "Specified power charging",
    VPP_WORK_MODE_SPECIFIED_POWER_DISCHARGE: "Specified power discharge",
    VPP_WORK_MODE_BATTERY_IDLE: "Battery idle",
    VPP_WORK_MODE_CHARGE_DISCHARGE_TIME: "Charging and discharge time period",
}

VPP_WORD_MODE = "vpp_work_mode"
LOAD_FIRST_STOP_SOC = "load_first_stop_soc"
CHARGE_STOP_SOC = "charge_stop_soc"
GRID_FIRST_STOP_SOC = "grid_first_stop_soc"
CHARGE_POWER_SET = "charge_power_set"
DISCHARGE_POWER_SET = "discharge_power_set"
CD_PERIOD_TIMES2 = "cd_period_times2"


PROPERTIES = {
    LOAD_FIRST_STOP_SOC: "LoadFirstStopSOC",
    CHARGE_STOP_SOC: "ChargeStopSOC",
    GRID_FIRST_STOP_SOC: "GridFirstStopSOC",
    CHARGE_POWER_SET: "ChargePowerSet",
    DISCHARGE_POWER_SET: "DischargePowerSet",
    CD_PERIOD_TIMES2: "CDPeriodTimes2",
    VPP_WORD_MODE: "VPPWorkMode",
}

ATTR_AUTH_LANGUAGE = "page_language"
ATTR_REDIRECTION_URL = "redirection_url"
SUPPORTED_LANGUAGES = [("en_US", "English"), ("zh_CN", "Chinese")]

CLIENT_ID = "W4lHyHTK"
