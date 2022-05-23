"""Slack platform for switch component."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SlackEntity
from .const import DATA_CLIENT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Slack switch."""
    async_add_entities(
        [
            SlackSwitchEntity(
                hass.data[DOMAIN][entry.entry_id][DATA_CLIENT],
                SwitchEntityDescription(
                    key="status",
                    name="Status",
                ),
                entry,
            )
        ],
        True,
    )


class SlackSwitchEntity(SlackEntity, SwitchEntity):
    """Representation of a Slack switch."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._client.users_setPresence(presence="away")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._client.users_setPresence(presence="auto")

    async def async_update(self) -> None:
        """Get the latest status."""
        status = await self._client.users_getPresence(user=self._client.user_id)
        self._attr_is_on = status["presence"] == "active"
