"""Support for Google Mail Sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from googleapiclient.http import HttpRequest

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GoogleMailConfigEntry
from .entity import GoogleMailEntity

SCAN_INTERVAL = timedelta(minutes=15)

SENSOR_TYPE = SensorEntityDescription(
    key="vacation_end_date",
    translation_key="vacation_end_date",
    device_class=SensorDeviceClass.TIMESTAMP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleMailConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Google Mail sensor."""
    async_add_entities([GoogleMailSensor(entry.runtime_data, SENSOR_TYPE)], True)


class GoogleMailSensor(GoogleMailEntity, SensorEntity):
    """Representation of a Google Mail sensor."""

    async def async_update(self) -> None:
        """Get the vacation data."""
        service = await self.auth.get_resource()
        settings: HttpRequest = service.users().settings().getVacation(userId="me")
        data: dict = await self.hass.async_add_executor_job(settings.execute)

        if data["enableAutoReply"] and (end := data.get("endTime")):
            value = datetime.fromtimestamp(int(end) / 1000, tz=UTC)
        else:
            value = None
        self._attr_native_value = value
