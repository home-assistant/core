"""Sensor platform for FireServiceRota integration."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN as FIRESERVICEROTA_DOMAIN
from .coordinator import FireServiceConfigEntry, FireServiceRotaClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FireServiceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up FireServiceRota sensor based on a config entry."""
    async_add_entities([IncidentsSensor(entry.runtime_data.client)])


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class IncidentsSensor(RestoreEntity, SensorEntity):
    """Representation of FireServiceRota incidents sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "incidents"

    def __init__(self, client: FireServiceRotaClient) -> None:
        """Initialize."""
        self._client = client
        self._entry_id = self._client.entry_id
        self._attr_unique_id = f"{self._client.unique_id}_Incidents"
        self._state: str | None = None
        self._state_attributes: dict[str, Any] = {}

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if (
            "prio" in self._state_attributes
            and self._state_attributes["prio"][0] == "a"
        ):
            return "mdi:ambulance"

        return "mdi:fire-truck"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return available attributes for sensor."""
        attr: dict[str, Any] = {}

        if not (data := self._state_attributes):
            return attr

        for value in (
            "id",
            "trigger",
            "created_at",
            "message_to_speech_url",
            "prio",
            "type",
            "responder_mode",
            "can_respond_until",
            "task_ids",
        ):
            if data.get(value):
                attr[value] = data[value]

            if "address" not in data:
                continue

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
        """Run when about to be added to hass."""
        await super().async_added_to_hass()

        if state := await self.async_get_last_state():
            self._state = state.state
            self._state_attributes = state.attributes
            if "id" in self._state_attributes:
                self._client.incident_id = self._state_attributes["id"]
            _LOGGER.debug("Restored entity 'Incidents' to: %s", self._state)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{FIRESERVICEROTA_DOMAIN}_{self._entry_id}_update",
                self.client_update,
            )
        )

    @callback
    def client_update(self) -> None:
        """Handle updated data from the data client."""
        data = self._client.websocket.incident_data
        if not data or "body" not in data:
            return

        self._state = data["body"]
        self._state_attributes = data
        if "id" in self._state_attributes:
            self._client.incident_id = self._state_attributes["id"]
        self.async_write_ha_state()
