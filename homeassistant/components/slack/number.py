"""Slack platform for select component."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlackEntity
from .const import DATA_CLIENT, DOMAIN

NUMBER_TYPE = NumberEntityDescription(
    key="do_not_disturb_period",
    name="Do Not Disturb Period",
    icon="mdi:clock",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Slack select."""
    async_add_entities(
        [
            SlackNumberEntity(
                hass.data[DOMAIN][entry.entry_id][DATA_CLIENT],
                NUMBER_TYPE,
                entry,
            )
        ]
    )


class SlackNumberEntity(SlackEntity, NumberEntity):
    """Representation of a Slack number entity."""

    _attr_native_value = 60

    async def async_set_native_value(self, value: float) -> None:
        """Select lamp mode."""
        await self._client.dnd_setSnooze(num_minutes=value)
