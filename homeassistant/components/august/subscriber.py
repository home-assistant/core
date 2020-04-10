"""Base class for August entity."""


from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval


class AugustSubscriberMixin:
    """Base implementation for a subscriber."""

    def __init__(self, hass, update_interval):
        """Initialize an subscriber."""
        super().__init__()
        self._hass = hass
        self._update_interval = update_interval
        self._subscriptions = {}
        self._unsub_interval = None

    @callback
    def async_subscribe_device_id(self, device_id, update_callback):
        """Add an callback subscriber."""
        if not self._subscriptions:
            self._unsub_interval = async_track_time_interval(
                self._hass, self._async_refresh, self._update_interval
            )
        self._subscriptions.setdefault(device_id, []).append(update_callback)

    @callback
    def async_unsubscribe_device_id(self, device_id, update_callback):
        """Remove a callback subscriber."""
        self._subscriptions[device_id].remove(update_callback)
        if not self._subscriptions[device_id]:
            del self._subscriptions[device_id]
        if not self._subscriptions:
            self._unsub_interval()
            self._unsub_interval = None

    @callback
    def async_signal_device_id_update(self, device_id):
        """Call the callbacks for a device_id."""
        if not self._subscriptions.get(device_id):
            return

        for update_callback in self._subscriptions[device_id]:
            update_callback()
