"""Constants for the Hinen Power integration."""

import logging

DOMAIN = "hinen_power"
MANUFACTURER = "Hinen"

HOST = "host"

LOGGER = logging.getLogger(__package__)

ATTR_REGION_CODE = "region_code"
ATTR_ACCOUNT_ID = "account_id"
ATTR_STATUS = "status"
ATTR_ALERT_STATUS = "alert_status"
ATTR_DEVICE_NAME = "device_name"
ATTR_SERIAL_NUMBER = "serial_number"

REGION_CODE = "regionCode"
CUMULATIVE_CONSUMPTION = "cumulative_consumption"
CUMULATIVE_PRODUCTION_ACTIVE = "cumulative_production_active"
CUMULATIVE_GRID_FEED_IN = "cumulative_grid_feed_in"
TOTAL_CHARGING_ENERGY = "total_charging_energy"
TOTAL_DISCHARGING_ENERGY = "total_discharging_energy"

PROPERTIES = {
    CUMULATIVE_CONSUMPTION: "CumulativeConsumption",
    CUMULATIVE_PRODUCTION_ACTIVE: "CumulativeProductionActive",
    CUMULATIVE_GRID_FEED_IN: "CumulativeGridFeedIn",
    TOTAL_CHARGING_ENERGY: "TotalChargingEnergy",
    TOTAL_DISCHARGING_ENERGY: "TotalDischargingEnergy",
}

ATTR_AUTH_LANGUAGE = "page_language"
SUPPORTED_LANGUAGES = [("en_US", "English"), ("zh_CN", "简体中文")]
