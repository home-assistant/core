"""Light platform for Kaku RC 32 bit dim control."""

from typing import Any

from rf_protocols.commands.ook import OOKCommand

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
    FREQUENCY_HZ,
    REPEAT_COUNT,
    format_device_summary,
    get_kaku_timings,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the optional dimmer light entity."""
    if not config_entry.data.get(CONF_DIM, False):
        return

    async_add_entities([KakuDimmerLight(config_entry)])


class KakuDimmerLight(LightEntity, RestoreEntity):
    """Brightness control for Kaku devices."""

    _attr_has_entity_name = True
    _attr_name = "Brightness"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the dimmer light."""
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._device_id: int = entry.data[CONF_DEVICE_ID]
        self._channel: int = entry.data[CONF_CHANNEL]
        self._group: bool = entry.data.get(CONF_GROUP, False)
        self._attr_unique_id = f"{entry.entry_id}_dim"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Kaku",
            model="Kaku RC 32 bit",
            name=entry.title,
            sw_version=format_device_summary(
                self._device_id, self._channel, self._group, True
            ),
        )
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_brightness = 255

    async def async_added_to_hass(self) -> None:
        """Subscribe to transmitter state and restore last light state."""
        await super().async_added_to_hass()

        transmitter_entity_id = er.async_validate_entity_id(
            er.async_get(self.hass), self._transmitter
        )

        @callback
        def _async_transmitter_state_changed(
            event: Event[EventStateChangedData],
        ) -> None:
            new_state = event.data["new_state"]
            available = new_state is not None and new_state.state != STATE_UNAVAILABLE
            if available != self._attr_available:
                self._attr_available = available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [transmitter_entity_id],
                _async_transmitter_state_changed,
            )
        )

        transmitter_state = self.hass.states.get(transmitter_entity_id)
        self._attr_available = (
            transmitter_state is not None
            and transmitter_state.state != STATE_UNAVAILABLE
        )

        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON
            last_brightness = last_state.attributes.get("brightness")
            if isinstance(last_brightness, int):
                self._attr_brightness = last_brightness

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on and update brightness level."""
        brightness = kwargs.get("brightness")
        if isinstance(brightness, int):
            self._attr_brightness = max(1, min(255, brightness))
        elif self._attr_brightness <= 0:
            self._attr_brightness = 255

        await self._async_send(brightness=self._attr_brightness)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmer off."""
        await self._async_send(brightness=None)
        self._attr_is_on = False
        self._attr_brightness = 0
        self.async_write_ha_state()

    async def _async_send(self, *, brightness: int | None = None) -> None:
        """Send dimming command using dimlevel or on/off.

        When brightness is provided, uses dimlevel parameter with on=None.
        When brightness is None (off), uses on=False with dimlevel=None.
        """
        if brightness is not None:
            dimlevel = max(1, min(100, round(brightness * 100 / 255)))
            # Use dimming with dimlevel, set on=None
            timings = get_kaku_timings(
                self._device_id,
                self._channel,
                group=self._group,
                on=None,
                dimlevel=dimlevel,
                frame_repeats=REPEAT_COUNT,
            )
        else:
            # Turn off using on=False
            timings = get_kaku_timings(
                self._device_id,
                self._channel,
                group=self._group,
                on=False,
                dimlevel=None,
                frame_repeats=REPEAT_COUNT,
            )
            self._attr_brightness = 0
        command = OOKCommand(
            frequency=FREQUENCY_HZ,
            timings=timings,
            repeat_count=REPEAT_COUNT,
        )
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
