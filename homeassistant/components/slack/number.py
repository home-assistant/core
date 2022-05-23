"""Slack platform for select component."""

from __future__ import annotations

from slack import WebClient

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TIME_MINUTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlackEntity
from .const import DATA_CLIENT, DOMAIN


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
                NumberEntityDescription(
                    key="do_not_disturb_period",
                    name="Do Not Disturb Period",
                    icon="mdi:clock",
                    unit_of_measurement=TIME_MINUTES,
                    step=1,
                ),
                entry,
            )
        ]
    )


class SlackNumberEntity(SlackEntity, NumberEntity):
    """Representation of a Slack number entity."""

    def __init__(
        self,
        client: WebClient,
        description: NumberEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a Slack number entity."""
        super().__init__(client, entry)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}_{client.user_id}"
        self._attr_value = 60

    async def async_set_value(self, value: float) -> None:
        """Select lamp mode."""
        await self._client.dnd_setSnooze(num_minutes=value)
