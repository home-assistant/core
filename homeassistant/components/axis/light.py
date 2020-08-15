"""Support for Axis lights."""

from axis.event_stream import CLASS_LIGHT

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .axis_base import AxisEventBase
from .const import DOMAIN as AXIS_DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up a Axis light."""
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    if not device.api.vapix.light_control:
        return

    @callback
    def async_add_sensor(event_id):
        """Add light from Axis device."""
        event = device.api.event[event_id]

        if event.CLASS == CLASS_LIGHT and event.TYPE == "Light":
            async_add_entities([AxisLight(event, device)], True)

    device.listeners.append(
        async_dispatcher_connect(hass, device.signal_new_event, async_add_sensor)
    )


class AxisLight(AxisEventBase, LightEntity):
    """Representation of a light Axis event."""

    def __init__(self, event, device):
        """Initialize the Axis light."""
        super().__init__(event, device)

        self.light_id = f"led{self.event.id}"

        self.current_intensity = 0
        self.max_intensity = 0

        self._features = SUPPORT_BRIGHTNESS

    async def async_added_to_hass(self) -> None:
        """Subscribe lights events."""
        await super().async_added_to_hass()

        def get_light_capabilities():
            """Get light capabilities."""
            current_intensity = self.device.api.vapix.light_control.get_current_intensity(
                self.light_id
            )
            self.current_intensity = current_intensity["data"]["intensity"]

            max_intensity = self.device.api.vapix.light_control.get_valid_intensity(
                self.light_id
            )
            self.max_intensity = max_intensity["data"]["ranges"][0]["high"]

        await self.hass.async_add_executor_job(get_light_capabilities)

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def name(self):
        """Return the name of the light."""
        light_type = self.device.api.vapix.light_control[self.light_id].light_type
        return f"{self.device.name} {light_type} {self.event.TYPE} {self.event.id}"

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.event.is_tripped

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int((self.current_intensity / self.max_intensity) * 255)

    def turn_on(self, **kwargs):
        """Turn on light."""
        if not self.is_on:
            self.device.api.vapix.light_control.activate_light(self.light_id)

        if ATTR_BRIGHTNESS in kwargs:
            intensity = int((kwargs[ATTR_BRIGHTNESS] / 255) * self.max_intensity)
            self.device.api.vapix.light_control.set_manual_intensity(
                self.light_id, intensity
            )

    def turn_off(self, **kwargs):
        """Turn off light."""
        if self.is_on:
            self.device.api.vapix.light_control.deactivate_light(self.light_id)

    def update(self):
        """Update brightness."""
        current_intensity = self.device.api.vapix.light_control.get_current_intensity(
            self.light_id
        )
        self.current_intensity = current_intensity["data"]["intensity"]

    @property
    def should_poll(self):
        """Brightness needs polling."""
        return True
