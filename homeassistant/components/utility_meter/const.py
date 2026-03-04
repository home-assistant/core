"""Constants for the utility meter component."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, TypedDict

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .sensor import UtilityMeterSensor

DOMAIN = "utility_meter"

QUARTER_HOURLY = "quarter-hourly"
HOURLY = "hourly"
DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"
BIMONTHLY = "bimonthly"
QUARTERLY = "quarterly"
YEARLY = "yearly"

METER_TYPES = [
    QUARTER_HOURLY,
    HOURLY,
    DAILY,
    WEEKLY,
    MONTHLY,
    BIMONTHLY,
    QUARTERLY,
    YEARLY,
]

DATA_UTILITY: HassKey[dict[str, MeterInformation]] = HassKey(DOMAIN)
DATA_TARIFF_SENSORS: Final = "utility_meter_sensors"

CONF_METER = "meter"
CONF_SOURCE_SENSOR: Final = "source"
CONF_METER_TYPE = "cycle"
CONF_METER_OFFSET: Final = "offset"
CONF_METER_DELTA_VALUES: Final = "delta_values"
CONF_METER_NET_CONSUMPTION: Final = "net_consumption"
CONF_METER_PERIODICALLY_RESETTING: Final = "periodically_resetting"
CONF_PAUSED = "paused"
CONF_TARIFFS = "tariffs"
CONF_TARIFF = "tariff"
CONF_TARIFF_ENTITY: Final = "tariff_entity"
CONF_CRON_PATTERN = "cron"
CONF_SENSOR_ALWAYS_AVAILABLE: Final = "always_available"

ATTR_TARIFF = "tariff"
ATTR_TARIFFS = "tariffs"
ATTR_VALUE = "value"
ATTR_CRON_PATTERN = "cron pattern"
ATTR_NEXT_RESET = "next_reset"

SIGNAL_START_PAUSE_METER = "utility_meter_start_pause"
SIGNAL_RESET_METER = "utility_meter_reset"

SERVICE_RESET = "reset"
SERVICE_CALIBRATE_METER = "calibrate"


class MeterInformation(TypedDict, total=False):
    """Meter information."""

    always_available: bool
    delta_values: bool
    name: str
    net_consumption: bool
    offset: timedelta
    periodically_resetting: bool
    source: str
    tariff_entity: str | None
    unique_id: str
    utility_meter_sensors: list[UtilityMeterSensor]
