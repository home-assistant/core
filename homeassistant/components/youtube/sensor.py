"""Support for Google Mail Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AsyncConfigEntryAuth
from .const import CONF_CHANNELS, DOMAIN
from .entity import YouTubeEntity

SCAN_INTERVAL = timedelta(minutes=15)


@dataclass
class YouTubeMixin:
    """Mixin for required keys."""

    value_fn: Callable[[Any], StateType | datetime]


@dataclass
class YouTubeSensorEntityDescription(SensorEntityDescription, YouTubeMixin):
    """Describes Picnic sensor entity."""


SENSOR_TYPE = YouTubeSensorEntityDescription(
    key="live",
    name="Live",
    icon="mdi:clock",
    value_fn=lambda channel: channel["snippet"]["title"],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Mail sensor."""
    channel_ids = entry.options[CONF_CHANNELS]
    async_config_entry_auth: AsyncConfigEntryAuth = hass.data[DOMAIN][entry.entry_id]
    await async_config_entry_auth.get_resource()

    def _get_channels() -> list[dict[str, Any]]:
        """Get profile from inside the executor."""
        request = (
            build(
                "youtube",
                "v3",
                credentials=Credentials(entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]),
            )
            .channels()
            .list(
                part="snippet,contentDetails,statistics",
                id=",".join(channel_ids),
                maxResults=50,
            )
        )
        return request.execute()["items"]

    channels = await hass.async_add_executor_job(_get_channels)
    async_add_entities(
        [
            YouTubeSensor(hass.data[DOMAIN][entry.entry_id], SENSOR_TYPE, channel)
            for channel in channels
        ],
        True,
    )


class YouTubeSensor(YouTubeEntity, SensorEntity):
    """Representation of a Google Mail sensor."""

    def __init__(
        self,
        auth: AsyncConfigEntryAuth,
        description: EntityDescription,
        channel: dict[str, Any],
    ) -> None:
        super().__init__(auth, description)
        self._channel = channel
        channel_id = channel["id"]
        self._attr_unique_id = (
            f"{auth.oauth_session.config_entry.entry_id}_{channel_id}_{description.key}"
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        # return self.entity_description.value_fn(self._channel)
        name = self._channel["snippet"]["title"]
        channel_id = self._channel["id"]
        return f"{name}{channel_id}"
