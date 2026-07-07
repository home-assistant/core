"""Sandbox proxy for ``sensor`` entities."""

from datetime import date, datetime
from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.util import dt as dt_util

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxSensorEntity(SandboxProxyEntity, SensorEntity):
    """Proxy for a ``sensor`` entity in a sandbox."""

    @property
    @override
    def native_value(self) -> datetime | date | str | int | float | None:
        """Return the cached state as the sensor's native value.

        The sandbox pushes the already-formatted state string; timestamp /
        date sensors must hand ``SensorEntity`` a real ``datetime`` /
        ``date`` back or its ``state`` property dies on ``value.tzinfo``.
        An unparsable string (``unknown`` and friends) degrades to None.
        """
        value = self._state_cache.get("state")
        if not isinstance(value, str):
            return value
        device_class = self.device_class
        if device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value)
        if device_class == SensorDeviceClass.DATE:
            return dt_util.parse_date(value)
        return value

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the cached unit of measurement."""
        return self._state_cache.get(
            ATTR_UNIT_OF_MEASUREMENT,
            self.description.capabilities.get(ATTR_UNIT_OF_MEASUREMENT),
        )
