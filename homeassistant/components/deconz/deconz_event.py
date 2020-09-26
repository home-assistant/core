"""Representation of a deCONZ remote."""
from pydeconz.sensor import Switch

from homeassistant.const import CONF_EVENT, CONF_ID, CONF_UNIQUE_ID
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .const import CONF_ANGLE, CONF_GESTURE, CONF_XY, LOGGER, NEW_SENSOR
from .deconz_device import DeconzBase

CONF_DECONZ_EVENT = "deconz_event"


async def async_setup_events(gateway) -> None:
    """Set up the deCONZ events."""

    @callback
    def async_add_sensor(sensors):
        """Create DeconzEvent."""
        for sensor in sensors:

            if not gateway.option_allow_clip_sensor and sensor.type.startswith("CLIP"):
                continue

            if sensor.type not in Switch.ZHATYPE or sensor.uniqueid in {
                event.unique_id for event in gateway.events
            }:
                continue

            new_event = DeconzEvent(sensor, gateway)
            gateway.hass.async_create_task(new_event.async_update_device_registry())
            gateway.events.append(new_event)

    gateway.listeners.append(
        async_dispatcher_connect(
            gateway.hass, gateway.async_signal_new_device(NEW_SENSOR), async_add_sensor
        )
    )

    async_add_sensor(
        [gateway.api.sensors[key] for key in sorted(gateway.api.sensors, key=int)]
    )


@callback
def async_unload_events(gateway) -> None:
    """Unload all deCONZ events."""
    for event in gateway.events:
        event.async_will_remove_from_hass()

    gateway.events.clear()


class DeconzEvent(DeconzBase):
    """When you want signals instead of entities.

    Stateless sensors such as remotes are expected to generate an event
    instead of a sensor entity in hass.
    """

    def __init__(self, device, gateway):
        """Register callback that will be used for signals."""
        super().__init__(device, gateway)

        self._device.register_callback(self.async_update_callback)

        self.device_id = None
        self.event_id = slugify(self._device.name)
        LOGGER.debug("deCONZ event created: %s", self.event_id)

    @property
    def device(self):
        """Return Event device."""
        return self._device

    @callback
    def async_will_remove_from_hass(self) -> None:
        """Disconnect event object when removed."""
        self._device.remove_callback(self.async_update_callback)

    @callback
    def async_update_callback(self, force_update=False, ignore_update=False):
        """Fire the event if reason is that state is updated."""
        if ignore_update or "state" not in self._device.changed_keys:
            return

        data = {
            CONF_ID: self.event_id,
            CONF_UNIQUE_ID: self.serial,
            CONF_EVENT: self._device.state,
        }

        if self._device.gesture is not None:
            data[CONF_GESTURE] = self._device.gesture

        if self._device.angle is not None:
            data[CONF_ANGLE] = self._device.angle

        if self._device.xy is not None:
            data[CONF_XY] = self._device.xy

        self.gateway.hass.bus.async_fire(CONF_DECONZ_EVENT, data)

    async def async_update_device_registry(self):
        """Update device registry."""
        device_registry = (
            await self.gateway.hass.helpers.device_registry.async_get_registry()
        )

        entry = device_registry.async_get_or_create(
            config_entry_id=self.gateway.config_entry.entry_id, **self.device_info
        )
        self.device_id = entry.id
