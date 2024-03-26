"""Slack platform for sensor component."""

from __future__ import annotations

from slack import WebClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import SlackEntity
from .const import ATTR_SNOOZE, DOMAIN, SLACK_DATA


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Slack select."""
    async_add_entities(
        [
            SlackSensorEntity(
                hass.data[DOMAIN][entry.entry_id][SLACK_DATA],
                SensorEntityDescription(
                    key="do_not_disturb_until",
                    translation_key="do_not_disturb_until",
                    device_class=SensorDeviceClass.TIMESTAMP,
                ),
                entry,
            )
        ],
        True,
    )


class SlackSensorEntity(SlackEntity, SensorEntity):
    """Representation of a Slack sensor."""

    _client: WebClient

    async def async_update(self) -> None:
        """Get the latest status."""
        if _time := (await self._client.dnd_info()).get(ATTR_SNOOZE):
            self._attr_native_value = dt_util.utc_from_timestamp(_time)
        else:
            self._attr_native_value = None
