"""Constants for the EnergyZero integration."""

from datetime import timedelta
import logging
from typing import Final

from energyzero import Interval

CONF_ELECTRICITY_PRICE_INTERVAL = "electricity_price_interval"
ELECTRICITY_INTERVALS = {"hourly": Interval.HOUR, "quarter_hourly": Interval.QUARTER}
DEFAULT_ELECTRICITY_PRICE_INTERVAL = "hourly"

DOMAIN: Final = "energyzero"
LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=10)
THRESHOLD_HOUR: Final = 14

SERVICE_TYPE_DEVICE_NAMES = {
    "today_energy": "Energy market price",
    "today_gas": "Gas market price",
}
