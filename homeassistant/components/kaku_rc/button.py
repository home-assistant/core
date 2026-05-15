"""Button platform for Kaku RC 32 bit."""

from rf_protocols.commands.ook import OOKCommand

from homeassistant.components.button import ButtonEntity
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CHANNEL,
    CONF_DEVICE_ID,
    CONF_DIM,
    CONF_GROUP,
    CONF_TRANSMITTER,
    DOMAIN,
    FREQUENCY_HZ,
    REPEAT_COUNT_LEARN,
    format_device_summary,
    get_kaku_timings,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Kaku RC 32 bit button platform."""
    # Only add learn/unlearn buttons for non-group devices
    # Group commands typically don't support individual learning/unlearning
    group = config_entry.data.get(CONF_GROUP, False)
    if not group:
        async_add_entities(
            [
                KakuLearnButton(config_entry),
                KakuUnlearnButton(config_entry),
            ]
        )


class KakuButtonBase(ButtonEntity):
    """Base class for Kaku learning buttons."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the button."""
        self._transmitter: str = entry.data[CONF_TRANSMITTER]
        self._device_id: int = entry.data[CONF_DEVICE_ID]
        self._channel: int = entry.data[CONF_CHANNEL]
        self._group: bool = entry.data.get(CONF_GROUP, False)
        self._dim: bool = entry.data.get(CONF_DIM, False)
        self._attr_unique_id = f"{entry.entry_id}_{self._button_type()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Kaku",
            model="Kaku RC 32 bit",
            name=entry.title,
            sw_version=format_device_summary(
                self._device_id, self._channel, self._group, self._dim
            ),
        )

    def _button_type(self) -> str:
        """Return button type identifier."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Subscribe to transmitter state."""
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

    async def async_press(self) -> None:
        """Press the button to send learn/unlearn signal."""
        await self._async_send()

    def _get_on_state(self) -> bool:
        """Return the on/off state to send for this button."""
        raise NotImplementedError

    async def _async_send(self) -> None:
        """Encode and send the Kaku command."""
        timings = get_kaku_timings(
            self._device_id,
            self._channel,
            group=self._group,
            on=self._get_on_state(),
            frame_repeats=REPEAT_COUNT_LEARN,
        )
        command = OOKCommand(
            frequency=FREQUENCY_HZ,
            timings=timings,
            repeat_count=REPEAT_COUNT_LEARN,
        )
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )


class KakuLearnButton(KakuButtonBase):
    """Button to learn/pair a Kaku socket."""

    _attr_icon = "mdi:wifi-sync"
    _attr_name = "Learn"

    def _button_type(self) -> str:
        return "learn"

    def _get_on_state(self) -> bool:
        return True


class KakuUnlearnButton(KakuButtonBase):
    """Button to unlearn/unpair a Kaku socket."""

    _attr_icon = "mdi:wifi-off"
    _attr_name = "Unlearn"

    def _button_type(self) -> str:
        return "unlearn"

    def _get_on_state(self) -> bool:
        return False
