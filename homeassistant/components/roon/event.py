"""Roon event entities."""

import logging
from typing import cast

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roon Event from Config Entry."""
    roon_server = hass.data[DOMAIN][config_entry.entry_id]
    event_entities = set()

    @callback
    def async_add_roon_volume_entity(player_data):
        """Add or update Roon event Entity."""
        dev_id = player_data["dev_id"]
        if dev_id in event_entities:
            return
        # new player!
        event_entity = RoonEventEntity(roon_server, player_data)
        event_entities.add(dev_id)
        async_add_entities([event_entity])

    # start listening for players to be added from the server component
    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, "roon_media_player", async_add_roon_volume_entity
        )
    )


class RoonEventEntity(EventEntity):
    """Representation of a Roon Event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["volume_up", "volume_down", "mute_toggle"]
    _attr_translation_key = "volume"

    def __init__(self, server, player_data):
        """Initialize the entity."""
        self._server = server
        self._player_data = player_data
        player_name = player_data["display_name"]
        self._attr_name = f"{player_name} roon volume"
        self._attr_unique_id = self._player_data["dev_id"]

        if self._player_data.get("source_controls"):
            dev_model = self._player_data["source_controls"][0].get("display_name")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            # Instead of setting the device name to the entity name, roon
            # should be updated to set has_entity_name = True, and set the entity
            # name to None
            name=cast(str | None, self.name),
            manufacturer="RoonLabs",
            model=dev_model,
            via_device=(DOMAIN, self._server.roon_id),
        )

    def _roonapi_volume_callback(
        self, control_key: str, event: str, value: int
    ) -> None:
        """Callbacks from the roon api with volume request."""

        if event == "set_mute":
            event = "mute_toggle"
        elif event == "set_volume":
            if value > 0:
                event = "volume_up"
            else:
                event = "volume_down"
        else:
            _LOGGER.debug("Received unsupported roon volume event %s", event)
            return

        self._trigger_event(event)
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register volume hooks with the roon api."""

        self._server.roonapi.register_volume_control(
            self.unique_id,
            self.name,
            self._roonapi_volume_callback,
            0,
            "incremental",
            0,
            0,
            0,
            False,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister volume hooks from the roon api."""
        self._server.roonapi.unregister_volume_control(self.unique_id)
