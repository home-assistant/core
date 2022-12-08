"""Slack platform for sensor component."""
from __future__ import annotations

from slack import WebClient
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from . import SlackEntity
from .const import ATTR_SNOOZE, CONF_DURATION, DOMAIN, SLACK_DATA

SERVICE_SET_DND = "set_dnd"


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
                    name="Do not disturb until",
                    icon="mdi:clock",
                    device_class=SensorDeviceClass.TIMESTAMP,
                ),
                entry,
            )
        ],
        True,
    )
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_DND,
        {
            vol.Required(CONF_DURATION): cv.positive_int,
        },
        "async_set_dnd",
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

    async def async_set_dnd(self, duration: int) -> None:
        """Set Do not Disturb status for to specified length of time."""
        await self._client.dnd_setSnooze(num_minutes=duration)
