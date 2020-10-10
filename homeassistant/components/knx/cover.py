"""Support for KNX/IP covers."""
from xknx.devices import Cover as XknxCover

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DEVICE_CLASS_BLIND,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_utc_time_change

from .const import DOMAIN
from .knx_entity import KnxEntity


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up cover(s) for KNX platform."""
    entities = []
    for device in hass.data[DOMAIN].xknx.devices:
        if isinstance(device, XknxCover):
            entities.append(KNXCover(device))
    async_add_entities(entities)


class KNXCover(KnxEntity, CoverEntity):
    """Representation of a KNX cover."""

    def __init__(self, device: XknxCover):
        """Initialize the cover."""
        super().__init__(device)

        self._unsubscribe_auto_updater = None

    @callback
    async def after_update_callback(self, device):
        """Call after device was updated."""
        self.async_write_ha_state()
        if self._device.is_traveling():
            self.start_auto_updater()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._device.supports_angle:
            return DEVICE_CLASS_BLIND
        return None

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION
        if self._device.supports_stop:
            supported_features |= SUPPORT_STOP
        if self._device.supports_angle:
            supported_features |= SUPPORT_SET_TILT_POSITION
        return supported_features

    @property
    def current_cover_position(self):
        """Return the current position of the cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        # In KNX 0 is open, 100 is closed.
        try:
            return 100 - self._device.current_position()
        except TypeError:
            return None

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._device.is_closed()

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._device.is_opening()

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._device.is_closing()

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._device.set_down()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._device.set_up()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        knx_position = 100 - kwargs[ATTR_POSITION]
        await self._device.set_position(knx_position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._device.stop()
        self.stop_auto_updater()

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position of cover."""
        if not self._device.supports_angle:
            return None
        try:
            return 100 - self._device.current_angle()
        except TypeError:
            return None

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        knx_tilt_position = 100 - kwargs[ATTR_TILT_POSITION]
        await self._device.set_angle(knx_tilt_position)

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
        if self._device.position_reached():
            self.stop_auto_updater()

        self.hass.add_job(self._device.auto_stop_if_necessary())
