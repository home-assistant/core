"""Support for KNX/IP covers."""
from xknx.devices import Cover as XknxCover

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_utc_time_change

from . import ATTR_DISCOVER_DEVICES, DATA_KNX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up covers for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXCover(device))
    async_add_entities(entities)


class KNXCover(CoverEntity):
    """Representation of a KNX cover."""

    def __init__(self, device: XknxCover):
        """Initialize the cover."""
        self.device = device
        self._unsubscribe_auto_updater = None

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    async def async_update(self):
        """Request a state update from KNX bus."""
        await self.device.sync()

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = (
            SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION | SUPPORT_STOP
        )
        if self.device.supports_angle:
            supported_features |= SUPPORT_SET_TILT_POSITION
        return supported_features

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.device.current_position()

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.device.is_closed()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if not self.device.is_closed():
            await self.device.set_down()
            self.start_auto_updater()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if not self.device.is_open():
            await self.device.set_up()
            self.start_auto_updater()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self.device.set_position(position)
            self.start_auto_updater()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.device.stop()
        self.stop_auto_updater()

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position of cover."""
        if not self.device.supports_angle:
            return None
        return self.device.current_angle()

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        if ATTR_TILT_POSITION in kwargs:
            tilt_position = kwargs[ATTR_TILT_POSITION]
            await self.device.set_angle(tilt_position)

    def start_auto_updater(self):
        """Start the autoupdater to update Home Assistant while cover is moving."""
        if self._unsubscribe_auto_updater is None:
            self._unsubscribe_auto_updater = async_track_utc_time_change(
                self.hass, self.auto_updater_hook
            )

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        self.async_write_ha_state()
        if self.device.position_reached():
            self.stop_auto_updater()

        self.hass.add_job(self.device.auto_stop_if_necessary())
