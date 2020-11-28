"""Switch platform for FireServiceRota integration."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DATA_CLIENT, DOMAIN as FIRESERVICEROTA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota switch based on a config entry."""
    client = hass.data[FIRESERVICEROTA_DOMAIN][entry.entry_id][DATA_CLIENT]

    async_add_entities([ResponseSwitch(client, entry)])


class ResponseSwitch(SwitchEntity):
    """Representation of an FireServiceRota switch."""

    def __init__(self, client, entry):
        """Initialize."""
        self._client = client
        self._unique_id = f"{entry.unique_id}_Response"
        self._entry_id = entry.entry_id

        self._state = None
        self._state_attributes = {}

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "Incident Response"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._state:
            return "mdi:run-fast"

        return "mdi:forum"

    @property
    def is_on(self) -> bool:
        """Get the assumed state of the switch."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this switch."""
        return self._unique_id

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self) -> object:
        """Return available attributes for switch."""
        attr = {}
        if not self._state_attributes:
            return attr

        data = self._state_attributes
        attr = {
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

        _LOGGER.debug("Set attributes of entity 'Response Switch' to '%s'", attr)
        return attr

    async def async_turn_on(self, **kwargs) -> None:
        """Send Acknowlegde response status."""
        await self.async_set_response(True)

    async def async_turn_off(self, **kwargs) -> None:
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
                f"{FIRESERVICEROTA_DOMAIN}_{self._entry_id}_update",
                self.client_update,
            )
        )

    @callback
    def client_update(self) -> None:
        """Handle updated incident data from the client."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> bool:
        """Update FireServiceRota response data."""
        data = await self._client.async_response_update()

        if not data or "status" not in data:
            return

        self._state = data["status"] == "acknowledged"
        self._state_attributes = data

        _LOGGER.debug("Set state of entity 'Response Switch' to '%s'", self._state)
