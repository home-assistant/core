"""Support for Axis binary sensors."""

from datetime import timedelta

from axis.event_stream import CLASS_INPUT, CLASS_OUTPUT

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import CONF_TRIGGER_TIME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from .axis_base import AxisEventBase
from .const import DOMAIN as AXIS_DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Axis binary sensor."""
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    @callback
    def async_add_sensor(event_id):
        """Add binary sensor from Axis device."""
        event = device.api.event.events[event_id]

        if event.CLASS != CLASS_OUTPUT:
            async_add_entities([AxisBinarySensor(event, device)], True)

    device.listeners.append(
        async_dispatcher_connect(hass, device.event_new_sensor, async_add_sensor)
    )


class AxisBinarySensor(AxisEventBase, BinarySensorDevice):
    """Representation of a binary Axis event."""

    def __init__(self, event, device):
        """Initialize the Axis binary sensor."""
        super().__init__(event, device)
        self.remove_timer = None

    @callback
    def update_callback(self, no_delay=False):
        """Update the sensor's state, if needed.

        Parameter no_delay is True when device_event_reachable is sent.
        """
        delay = self.device.config_entry.options[CONF_TRIGGER_TIME]

        if self.remove_timer is not None:
            self.remove_timer()
            self.remove_timer = None

        if self.is_on or delay == 0 or no_delay:
            self.async_schedule_update_ha_state()
            return

        @callback
        def _delay_update(now):
            """Timer callback for sensor update."""
            self.async_schedule_update_ha_state()
            self.remove_timer = None

        self.remove_timer = async_track_point_in_utc_time(
            self.hass, _delay_update, utcnow() + timedelta(seconds=delay)
        )

    @property
    def is_on(self):
        """Return true if event is active."""
        return self.event.is_tripped

    @property
    def name(self):
        """Return the name of the event."""
        if (
            self.event.CLASS == CLASS_INPUT
            and self.event.id
            and self.device.api.vapix.ports[self.event.id].name
        ):
            return (
                f"{self.device.name} {self.device.api.vapix.ports[self.event.id].name}"
            )

        return super().name
