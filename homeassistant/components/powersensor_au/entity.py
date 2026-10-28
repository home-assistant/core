"""Base entity for the Powersensor integration."""

from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

# Mark an entity unavailable when no update has arrived for this long.  Plugs
# report every second.  Sensors report every 30 seconds, relayed through a plug
# over Bluetooth, so they are allowed to miss several reports in a row.
PLUG_UPDATE_TIMEOUT = timedelta(seconds=60)
SENSOR_UPDATE_TIMEOUT = timedelta(seconds=300)


class PowersensorEntity(Entity):
    """Base class for entities fed by a Powersensor device's data signal.

    Subscribes to the dispatcher signal for one device and event, and marks the
    entity unavailable when no update has arrived within the timeout.
    Subclasses apply each pushed message to their own state, and set the
    timeout for their type of device.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _update_timeout: timedelta

    def __init__(
        self,
        mac: str,
        signal: str,
    ) -> None:
        """Initialize the entity."""
        self._has_recently_received_update_message = False
        self._mac = mac
        self._remove_unavailability_tracker: Callable[[], None] | None = None
        self._signal = signal

    @property
    @abstractmethod
    @override
    def device_info(self) -> DeviceInfo:
        """Return device info. Subclasses must implement."""

    @property
    @override
    def available(self) -> bool:
        """Return True when at least one update has been received recently."""
        return self._has_recently_received_update_message

    def _schedule_unavailable(self) -> None:
        """(Re-)schedule the unavailability timer."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_call_later(
            self.hass,
            self._update_timeout,
            self._async_make_unavailable,
        )

    @callback
    def _async_make_unavailable(self, _now: datetime) -> None:
        """Mark entity as unavailable when the timeout fires."""
        self._has_recently_received_update_message = False
        self.async_write_ha_state()

    def _cancel_unavailability_tracker(self) -> None:
        """Cancel the unavailability timer if one is scheduled."""
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
            self._remove_unavailability_tracker = None

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the data-update signal and register the unavailability timer."""
        await super().async_added_to_hass()
        self._has_recently_received_update_message = False
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_update)
        )
        self.async_on_remove(self._cancel_unavailability_tracker)

    @callback
    def _handle_update(self, event: str | None, message: dict[str, Any]) -> None:
        """Handle a pushed data update from the dispatcher."""
        was_available = self._has_recently_received_update_message
        self._has_recently_received_update_message = True
        needs_write = self._update_from_message(message)
        self._schedule_unavailable()
        if needs_write or not was_available:
            self.async_write_ha_state()

    @abstractmethod
    def _update_from_message(self, message: dict[str, Any]) -> bool:
        """Apply a pushed message to the entity's state.

        Return whether the state must be written.  An entity that becomes
        available again is written regardless.
        """
