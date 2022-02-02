"""Constants for the PECO Outage Counter integration."""
import logging

from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "peco"
_LOGGER = logging.getLogger(__name__)
COUNTY_LIST = [
    "BUCKS",
    "CHESTER",
    "DELAWARE",
    "MONTGOMERY",
    "PHILADELPHIA",
    "YORK",
    "TOTAL",
]
SCAN_INTERVAL = 5
ATTR_CUSTOMERS_OUT = "customers_out"
ATTR_PERCENT_CUSTOMERS_OUT = "percent_customers_out"
ATTR_OUTAGE_COUNT = "outage_count"
ATTR_CUSTOMERS_SERVED = "customers_served"
SENSOR_LIST = (
    SensorEntityDescription(key=ATTR_CUSTOMERS_OUT, name="{} Customers Out"),
    SensorEntityDescription(
        key=ATTR_PERCENT_CUSTOMERS_OUT, name="{} Percent Customers Out"
    ),
    SensorEntityDescription(key=ATTR_OUTAGE_COUNT, name="{} Outage Count"),
    SensorEntityDescription(key=ATTR_CUSTOMERS_SERVED, name="{} Customers Served"),
)
