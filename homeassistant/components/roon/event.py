"""Roon event entities."""
import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
        event_entity = RoonEventEntity(roon_server, player_data["display_name"])
        event_entities.add(dev_id)
        async_add_entities([event_entity])

    # start listening for players to be added from the server component
    async_dispatcher_connect(hass, "roon_media_player", async_add_roon_volume_entity)


class RoonEventEntity(EventEntity):
    """Representation of a Roon Event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["volume_up", "volume_down"]

    def __init__(self, server, name):
        """Initialize the entity."""
        self._server = server
        self._name = f"{name} roon volume"

    @property
    def name(self) -> str:
        """Return name for the entity."""
        return self._name

    @callback
    def _roonapi_volume_callback(self, control_key, event, value) -> None:
        """Callbacks from the roon api with volume request."""

        if event != "set_volume":
            _LOGGER.info("Received unsupported roon volume event %s", event)
            return

        if value > 0:
            event = "volume_up"
        else:
            event = "volume_down"

        self._trigger_event(event)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register volume hooks with the roon api."""

        self._server.roonapi.register_volume_control(
            self.entity_id,
            self._name,
            self._roonapi_volume_callback,
            0,
            "incremental",
            0,
            0,
            0,
            False,
        )
