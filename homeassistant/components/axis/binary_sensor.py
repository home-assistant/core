"""Support for Axis binary sensors."""

from datetime import timedelta

from axis.event_stream import CLASS_INPUT, CLASS_OUTPUT

from homeassistant.components.binary_sensor import BinarySensorEntity
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
        event = device.api.event[event_id]

        if event.CLASS != CLASS_OUTPUT:
            async_add_entities([AxisBinarySensor(event, device)], True)

    device.listeners.append(
        async_dispatcher_connect(hass, device.signal_new_event, async_add_sensor)
    )


class AxisBinarySensor(AxisEventBase, BinarySensorEntity):
    """Representation of a binary Axis event."""

    def __init__(self, event, device):
        """Initialize the Axis binary sensor."""
        super().__init__(event, device)
        self.cancel_scheduled_update = None

    @callback
    def update_callback(self, no_delay=False):
        """Update the sensor's state, if needed.

        Parameter no_delay is True when device_event_reachable is sent.
        """

        @callback
        def scheduled_update(now):
            """Timer callback for sensor update."""
            self.cancel_scheduled_update = None
            self.async_write_ha_state()

        if self.cancel_scheduled_update is not None:
            self.cancel_scheduled_update()
            self.cancel_scheduled_update = None

        if self.is_on or self.device.option_trigger_time == 0 or no_delay:
            self.async_write_ha_state()
            return

        self.cancel_scheduled_update = async_track_point_in_utc_time(
            self.hass,
            scheduled_update,
            utcnow() + timedelta(seconds=self.device.option_trigger_time),
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
