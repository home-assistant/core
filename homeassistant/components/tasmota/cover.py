"""Support for Tasmota covers."""

from hatasmota import const as tasmota_const

from homeassistant.components import cover
from homeassistant.components.cover import CoverEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_REMOVE_DISCOVER_COMPONENT
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota cover dynamically through discovery."""

    @callback
    def async_discover(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota cover."""
        async_add_entities(
            [TasmotaCover(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(cover.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(cover.DOMAIN),
        async_discover,
    )


class TasmotaCover(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    CoverEntity,
):
    """Representation of a Tasmota cover."""

    def __init__(self, **kwds):
        """Initialize the Tasmota cover."""
        self._direction = None
        self._position = None

        super().__init__(
            **kwds,
        )

    @callback
    def state_updated(self, state, **kwargs):
        """Handle state updates."""
        self._direction = kwargs["direction"]
        self._position = kwargs["position"]
        self.async_write_ha_state()

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._position

    @property
    def supported_features(self):
        """Flag supported features."""
        return (
            cover.SUPPORT_OPEN
            | cover.SUPPORT_CLOSE
            | cover.SUPPORT_STOP
            | cover.SUPPORT_SET_POSITION
        )

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._direction == tasmota_const.SHUTTER_DIRECTION_UP

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._direction == tasmota_const.SHUTTER_DIRECTION_DOWN

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if self._position is None:
            return None
        return self._position == 0

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._tasmota_entity.open()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        self._tasmota_entity.close()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[cover.ATTR_POSITION]
        self._tasmota_entity.set_position(position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        self._tasmota_entity.stop()
