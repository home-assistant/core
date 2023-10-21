"""Roon event entities."""
import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)


class RoonEventEntity(EventEntity):
    """Representation of a Roon Event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["volume_up", "volume_down"]

    def __init__(self, server, name):
        """Initialize the entity."""
        self._server = server
        self._name = f"{name} volume control"

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
