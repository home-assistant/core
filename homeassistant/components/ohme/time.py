"""Platform for time integration."""

from __future__ import annotations

import asyncio
from datetime import time as dt_time
import logging

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR_CHARGESESSIONS,
    COORDINATOR_SCHEDULES,
    DATA_CLIENT,
    DATA_COORDINATORS,
    DOMAIN,
)
from .entity import OhmeEntity
from .utils import session_in_progress

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches and configure coordinator."""
    account_id = config_entry.data["email"]

    coordinators = hass.data[DOMAIN][account_id][DATA_COORDINATORS]
    client = hass.data[DOMAIN][account_id][DATA_CLIENT]

    numbers = [
        TargetTime(
            coordinators[COORDINATOR_CHARGESESSIONS],
            coordinators[COORDINATOR_SCHEDULES],
            hass,
            client,
        )
    ]

    async_add_entities(numbers, update_before_add=True)


class TargetTime(OhmeEntity, TimeEntity):
    """Target time sensor."""

    _attr_translation_key = "target_time"
    _attr_id = "target_time"
    _attr_icon = "mdi:alarm-check"

    def __init__(
        self, coordinator, coordinator_schedules, hass: HomeAssistant, client
    ) -> None:
        """Initialise target time sensor."""
        super().__init__(coordinator, hass, client)

        self.coordinator_schedules = coordinator_schedules

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator_schedules.async_add_listener(
                self._handle_coordinator_update, None
            )
        )

    async def async_set_value(self, value: dt_time) -> None:
        """Update the current value."""
        # If session in progress, update this session, if not update the first schedule
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            await self._client.async_apply_session_rule(
                target_time=(int(value.hour), int(value.minute))
            )
            await asyncio.sleep(1)
            await self.coordinator.async_refresh()
        else:
            await self._client.async_update_schedule(
                target_time=(int(value.hour), int(value.minute))
            )
            await asyncio.sleep(1)
            await self.coordinator_schedules.async_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get value from data returned from API by coordinator."""
        # Read with the same logic as setting
        target = None
        if session_in_progress(self.hass, self._client.email, self.coordinator.data):
            target = self.coordinator.data["appliedRule"]["targetTime"]
        elif self.coordinator_schedules.data:
            target = self.coordinator_schedules.data["targetTime"]

        if target:
            self._state = dt_time(
                hour=target // 3600, minute=(target % 3600) // 60, second=0
            )
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the state of the entity."""
        return self._state
