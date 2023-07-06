"""Constants for the dwd_weather_warnings integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "dwd_weather_warnings"

CONF_REGION_NAME: Final = "region_name"
CONF_REGION_IDENTIFIER: Final = "region_identifier"

ATTR_REGION_NAME: Final = "region_name"
ATTR_REGION_ID: Final = "region_id"
ATTR_LAST_UPDATE: Final = "last_update"
ATTR_WARNING_COUNT: Final = "warning_count"

API_ATTR_WARNING_NAME: Final = "event"
API_ATTR_WARNING_TYPE: Final = "event_code"
API_ATTR_WARNING_LEVEL: Final = "level"
API_ATTR_WARNING_HEADLINE: Final = "headline"
API_ATTR_WARNING_DESCRIPTION: Final = "description"
API_ATTR_WARNING_INSTRUCTION: Final = "instruction"
API_ATTR_WARNING_START: Final = "start_time"
API_ATTR_WARNING_END: Final = "end_time"
API_ATTR_WARNING_PARAMETERS: Final = "parameters"
API_ATTR_WARNING_COLOR: Final = "color"

CURRENT_WARNING_SENSOR: Final = "current_warning_level"
ADVANCE_WARNING_SENSOR: Final = "advance_warning_level"

DEFAULT_NAME: Final = "DWD Weather Warnings"
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=15)

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR]
