"""Switch platform for FireServiceRota integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    FireServiceConfigEntry,
    FireServiceRotaClient,
    FireServiceUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireServiceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FireServiceRota switch based on a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client

    async_add_entities([ResponseSwitch(coordinator, client, entry)])


class ResponseSwitch(SwitchEntity):
    """Representation of an FireServiceRota switch."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "incident_response"

    def __init__(
        self,
        coordinator: FireServiceUpdateCoordinator,
        client: FireServiceRotaClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._coordinator = coordinator
        self._client = client
        self._attr_unique_id = f"{entry.unique_id}_Response"
        self._entry_id = entry.entry_id

        self._state: bool | None = None
        self._state_attributes: dict[str, Any] = {}
        self._state_icon = None

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._state_icon == "acknowledged":
            return "mdi:run-fast"
        if self._state_icon == "rejected":
            return "mdi:account-off-outline"

        return "mdi:forum"

    @property
    def is_on(self) -> bool | None:
        """Get the assumed state of the switch."""
        return self._state

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        return self._client.on_duty

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return available attributes for switch."""
        attr: dict[str, Any] = {}
        if not self._state_attributes:
            return attr

        data = self._state_attributes
        return {
            key: data[key]
            for key in (
                "user_name",
                "assigned_skill_ids",
                "responded_at",
                "start_time",
                "status",
                "reported_status",
                "arrived_at_station",
                "available_at_incident_creation",
                "active_duty_function_ids",
            )
            if key in data
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send Acknowledge response status."""
        await self.async_set_response(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send Reject response status."""
        await self.async_set_response(False)

    async def async_set_response(self, value) -> None:
        """Send response status."""
        if not self._client.on_duty:
            _LOGGER.debug(
                "Cannot send incident response when not on duty",
            )
            return

        await self._client.async_set_response(value)
        self.client_update()

    async def async_added_to_hass(self) -> None:
        """Register update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry_id}_update",
                self.client_update,
            )
        )
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    @callback
    def client_update(self) -> None:
        """Handle updated incident data from the client."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update FireServiceRota response data."""
        data = await self._client.async_response_update()

        if not data or "status" not in data:
            return

        self._state = data["status"] == "acknowledged"
        self._state_attributes = data
        self._state_icon = data["status"]

        _LOGGER.debug("Set state of entity 'Response Switch' to '%s'", self._state)
