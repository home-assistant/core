"""Switch platform for KAKU (KlikAanKlikUit) RC."""

from typing import Any

from rf_protocols.commands.ook import OOKCommand

from homeassistant.components.radio_frequency import async_send_command
from homeassistant.components.switch import SwitchEntity
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
    """Set up the Kaku RC 32 bit switch platform."""
    async_add_entities([KakuSwitch(config_entry)])


class KakuSwitch(SwitchEntity, RestoreEntity):
    """A switch that controls a KAKU (KlikAanKlikUit) RC socket via RF."""

    _attr_assumed_state = True
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._device_id: int = entry.data[CONF_DEVICE_ID]
        self._channel: int = entry.data[CONF_CHANNEL]
        self._group: bool = entry.data.get(CONF_GROUP, False)
        self._dim: bool = entry.data.get(CONF_DIM, False)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="KlikAanKlikUit",
            model="KAKU RC",
            name=entry.title,
            sw_version=format_device_summary(
                self._device_id, self._channel, self._group, self._dim
            ),
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to transmitter state and restore last known switch state."""
        await super().async_added_to_hass()

        transmitter_entity_id = er.async_validate_entity_id(
            er.async_get(self.hass), self._transmitter
        )

        @callback
        def _async_transmitter_state_changed(
            event: Event[EventStateChangedData],
        ) -> None:
            new_state = event.data["new_state"]
            available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the socket on."""
        await self._async_send(on=True)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the socket off."""
        await self._async_send(on=False)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_send(self, *, on: bool) -> None:
        """Encode the Kaku command and transmit it."""
        timings = get_kaku_timings(
            self._device_id,
            self._channel,
            group=self._group,
            on=on,
            frame_repeats=REPEAT_COUNT,
        )
        command = OOKCommand(
            frequency=FREQUENCY_HZ,
            timings=timings,
            repeat_count=REPEAT_COUNT,
        )
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
