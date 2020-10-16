"""Sensor platform for FireServiceRota integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN as FIRESERVICEROTA_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up FireServiceRota sensor based on a config entry."""
    coordinator = hass.data[FIRESERVICEROTA_DOMAIN][entry.entry_id]

    async_add_entities([IncidentsSensor(coordinator, entry)])


class IncidentsSensor(RestoreEntity, Entity):
    """Representation of FireServiceRota incidents sensor."""

    def __init__(self, coordinator, entry):
        """Initialize."""
        self._coordinator = coordinator
        self._entry_id = entry.entry_id
        self._unique_id = entry.unique_id

        self._state = None
        self._state_attributes = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Incidents"

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:fire-truck"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self._unique_id}_Incidents"

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self) -> object:
        """Return available attributes for sensor."""
        attr = {}
        data = self._state_attributes

        if data:
            for value in (
                "trigger",
                "created_at",
                "message_to_speech_url",
                "prio",
                "type",
                "responder_mode",
                "can_respond_until",
            ):
                if data.get(value):
                    attr[value] = data[value]

            if "address" in data:
                for address_value in (
                    "latitude",
                    "longitude",
                    "address_type",
                    "formatted_address",
                ):
                    if address_value in data["address"]:
                        attr[address_value] = data["address"][address_value]

            return attr

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state:
            self._state = state.state
            self._state_attributes = state.attributes
            _LOGGER.debug("Restored entity 'Incidents' state to: %s", self._state)

        self.async_on_remove(self._coordinator.stop_listener)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FIRESERVICEROTA_DOMAIN}_{self._entry_id}_update",
                self.async_update,
            )
        )

    async def async_update(self) -> None:
        """Update using FireServiceRota data."""

        if not self._coordinator.incident_data:
            return

        if "body" in self._coordinator.incident_data:
            self._state = self._coordinator.incident_data["body"]
            self._state_attributes = self._coordinator.incident_data
            self.async_write_ha_state()

            _LOGGER.debug("Entity 'Incidents' state set to: %s", self._state)
