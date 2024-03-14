"""Helpers for sensor entities."""

from __future__ import annotations

from datetime import date, datetime
import logging

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from . import SensorDeviceClass

_LOGGER = logging.getLogger(__name__)


@callback
def async_parse_date_datetime(
    value: str, entity_id: str, device_class: SensorDeviceClass | str | None
) -> datetime | date | None:
    """Parse datetime string to a data or datetime."""
    if device_class == SensorDeviceClass.TIMESTAMP:
        if (parsed_timestamp := dt_util.parse_datetime(value)) is None:
            _LOGGER.warning("%s rendered invalid timestamp: %s", entity_id, value)
            return None

        if parsed_timestamp.tzinfo is None:
            _LOGGER.warning(
                "%s rendered timestamp without timezone: %s", entity_id, value
            )
            return None

        return parsed_timestamp

    # Date device class
    if (parsed_date := dt_util.parse_date(value)) is not None:
        return parsed_date

    _LOGGER.warning("%s rendered invalid date %s", entity_id, value)
    return None
