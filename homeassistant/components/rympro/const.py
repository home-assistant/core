"""Constants for the Read Your Meter Pro integration."""
from enum import Enum

DOMAIN = "rympro"


class MeterSensor(Enum):
    """Sensor types for each meter."""

    TOTAL_CONSUMPTION = "last_read"
    FORECAST = "consumption_forecast"
    DAILY_CONSUMPTION = "daily_consumption"
    MONTHLY_CONSUMPTION = "monthly_consumption"
