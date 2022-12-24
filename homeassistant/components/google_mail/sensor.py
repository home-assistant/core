"""Support for Google Mail Sensors."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GoogleMailEntity

SCAN_INTERVAL = timedelta(minutes=15)

SENSOR_TYPE = SensorEntityDescription(
    key="vacation_end_date",
    name="Vacation end date",
    icon="mdi:clock",
    device_class=SensorDeviceClass.TIMESTAMP,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Mail sensor."""
    async_add_entities([GoogleMailSensor(entry, SENSOR_TYPE)], True)


class GoogleMailSensor(GoogleMailEntity, SensorEntity):
    """Representation of a Google Mail sensor."""

    async def async_update(self) -> None:
        """Get the vacation data."""
        session: OAuth2Session = self.hass.data[DOMAIN].get(self.entry.entry_id)
        await session.async_ensure_token_valid()

        def _get_vacation() -> dict[str, Any]:
            """Get profile from inside the executor."""
            credentials = Credentials(self.entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN])
            users = build(  # pylint: disable=no-member
                "gmail", "v1", credentials=credentials
            ).users()
            return users.settings().getVacation(userId="me").execute()

        try:
            data = await self.hass.async_add_executor_job(_get_vacation)
        except RefreshError as ex:
            self.entry.async_start_reauth(self.hass)
            raise ex

        if data["enableAutoReply"]:
            value = datetime.fromtimestamp(int(data["endTime"]) / 1000, tz=timezone.utc)
        else:
            value = None
        self._attr_native_value = value
