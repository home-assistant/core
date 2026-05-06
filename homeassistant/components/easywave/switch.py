"""Switch platform for Easywave receivers."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Self

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from . import EasywaveConfigEntry, get_devices
from .const import (
    BUTTON_A,
    BUTTON_B,
    CONF_ENTRY_TYPE,
    CONF_RECEIVER_KIND,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_HEATING,
    RECEIVER_KIND_SWITCH,
)
from .entity import EasywaveDeviceEntry, EasywaveReceiverEntity

_LOGGER = logging.getLogger(__name__)

_HEATING_ACTUATOR_TIMEOUT = timedelta(hours=4)


@dataclass
class _SwitchRestoreData(ExtraStoredData):
    """Serialisable extra data for heating switch state restore."""

    last_sent: datetime | None

    def as_dict(self) -> dict[str, Any]:
        return {"last_sent": self.last_sent.isoformat() if self.last_sent else None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self | None:
        try:
            raw = data.get("last_sent")
            last_sent = dt_util.parse_datetime(raw) if raw else None
            return cls(last_sent=last_sent)
        except KeyError, ValueError:
            return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave switch entities."""
    for subentry in get_devices(entry):
        entry_type = subentry.data.get(CONF_ENTRY_TYPE)

        if entry_type == ENTRY_TYPE_RECEIVER:
            receiver_kind = subentry.data.get(CONF_RECEIVER_KIND)
            if receiver_kind in (RECEIVER_KIND_SWITCH, RECEIVER_KIND_HEATING):
                async_add_entities(
                    [EasywaveReceiverSwitch(entry, subentry)],
                )


class EasywaveReceiverSwitch(EasywaveReceiverEntity, SwitchEntity, RestoreEntity):
    """Represents an Easywave receiver controlled via the RX11 gateway."""

    _attr_assumed_state = True

    def __init__(
        self, entry: EasywaveConfigEntry, subentry: EasywaveDeviceEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, subentry, "switch")
        self._attr_is_on = False
        self._is_heating = (
            subentry.data.get(CONF_RECEIVER_KIND) == RECEIVER_KIND_HEATING
        )
        self._last_sent: datetime | None = None

        if self._is_heating:
            self._attr_translation_key = "heating"
        else:
            self._attr_translation_key = "receiver"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose last_sent timestamp as a visible state attribute."""
        if self._is_heating and self._last_sent is not None:
            return {"last_sent": self._last_sent.isoformat()}
        return {}

    @property
    def extra_restore_state_data(self) -> _SwitchRestoreData:
        """Persist the last-sent timestamp so we can detect long offline periods."""
        return _SwitchRestoreData(last_sent=self._last_sent)

    async def async_added_to_hass(self) -> None:
        """Restore the last known on/off state and start repeat timer for heating."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            self._attr_is_on = last_state.state == "on"
            self.async_write_ha_state()

        if self._is_heating:
            # Restore last-sent timestamp.
            if (extra := await self.async_get_last_extra_data()) is not None:
                restored = _SwitchRestoreData.from_dict(extra.as_dict())
                if restored is not None:
                    self._last_sent = restored.last_sent

            now = dt_util.utcnow()
            if self._last_sent is None:
                # No history: send immediately, then repeat every 4 h.
                self.hass.async_create_task(self._async_send_heating_command())
                self._start_repeat_timer()
            else:
                remaining = (
                    self._last_sent + _HEATING_ACTUATOR_TIMEOUT - now
                ).total_seconds()
                if remaining <= 0:
                    # Overdue: send immediately, then repeat every 4 h.
                    self.hass.async_create_task(self._async_send_heating_command())
                    self._start_repeat_timer()
                else:
                    # Schedule first send at exactly _last_sent + 4 h.
                    self.async_on_remove(
                        async_call_later(
                            self.hass,
                            remaining,
                            self._async_on_first_repeat,
                        )
                    )

    def _start_repeat_timer(self) -> None:
        """Start the regular 4-hour repeat timer."""
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._async_repeat_heating_command,
                _HEATING_ACTUATOR_TIMEOUT,
            )
        )

    @callback
    def _async_on_first_repeat(self, _now: Any) -> None:
        """Fire at _last_sent + 4 h, then start the regular interval."""
        self.hass.async_create_task(self._async_send_heating_command())
        self._start_repeat_timer()

    async def _async_send_heating_command(self) -> None:
        """Send the current on/off command and update last-sent timestamp."""
        if await self._send_command(BUTTON_A if self._attr_is_on else BUTTON_B):
            self._last_sent = dt_util.utcnow()

    @callback
    def _async_repeat_heating_command(self, _now: Any) -> None:
        """Resend the current on/off command so the heating actuator doesn't time out."""
        self.hass.async_create_task(self._async_send_heating_command())

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the receiver (send button A command)."""
        if await self._send_command(BUTTON_A):
            self._attr_is_on = True
            self._last_sent = dt_util.utcnow()
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send ON command to receiver %d", self._gateway_index
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the receiver (send button B command)."""
        if await self._send_command(BUTTON_B):
            self._attr_is_on = False
            self._last_sent = dt_util.utcnow()
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send OFF command to receiver %d", self._gateway_index
            )
