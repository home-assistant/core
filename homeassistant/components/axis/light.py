"""Support for Axis lights."""
from typing import Any

from axis.event_stream import CLASS_LIGHT, AxisBinaryEvent, AxisEvent

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .axis_base import AxisEventBase
from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a Axis light."""
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN][config_entry.unique_id]

    if (
        device.api.vapix.light_control is None
        or len(device.api.vapix.light_control) == 0
    ):
        return

    @callback
    def async_add_sensor(event_id):
        """Add light from Axis device."""
        event: AxisEvent = device.api.event[event_id]

        if event.CLASS == CLASS_LIGHT and event.TYPE == "Light":
            async_add_entities([AxisLight(event, device)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, device.signal_new_event, async_add_sensor)
    )


class AxisLight(AxisEventBase, LightEntity):
    """Representation of a light Axis event."""

    _attr_should_poll = True
    event: AxisBinaryEvent

    def __init__(self, event: AxisEvent, device: AxisNetworkDevice) -> None:
        """Initialize the Axis light."""
        super().__init__(event, device)

        self.light_id = f"led{self.event.id}"

        self.current_intensity = 0
        self.max_intensity = 0

        light_type = device.api.vapix.light_control[self.light_id].light_type
        self._attr_name = f"{light_type} {event.TYPE} {event.id}"

        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS

    async def async_added_to_hass(self) -> None:
        """Subscribe lights events."""
        await super().async_added_to_hass()

        current_intensity = (
            await self.device.api.vapix.light_control.get_current_intensity(
                self.light_id
            )
        )
        self.current_intensity = current_intensity["data"]["intensity"]

        max_intensity = await self.device.api.vapix.light_control.get_valid_intensity(
            self.light_id
        )
        self.max_intensity = max_intensity["data"]["ranges"][0]["high"]

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.event.is_tripped

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self.current_intensity / self.max_intensity) * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        if not self.is_on:
            await self.device.api.vapix.light_control.activate_light(self.light_id)

        if ATTR_BRIGHTNESS in kwargs:
            intensity = int((kwargs[ATTR_BRIGHTNESS] / 255) * self.max_intensity)
            await self.device.api.vapix.light_control.set_manual_intensity(
                self.light_id, intensity
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        if self.is_on:
            await self.device.api.vapix.light_control.deactivate_light(self.light_id)

    async def async_update(self) -> None:
        """Update brightness."""
        current_intensity = (
            await self.device.api.vapix.light_control.get_current_intensity(
                self.light_id
            )
        )
        self.current_intensity = current_intensity["data"]["intensity"]
