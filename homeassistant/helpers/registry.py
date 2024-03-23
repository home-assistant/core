"""Provide a base implementation for registries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from homeassistant.core import CoreState, HomeAssistant, callback

if TYPE_CHECKING:
    from .storage import Store

SAVE_DELAY = 10
SAVE_DELAY_LONG = 180


class BaseRegistry(ABC):
    """Class to implement a registry."""

    hass: HomeAssistant
    _store: Store

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the registry."""
        # Schedule the save past startup to avoid writing
        # the file while the system is starting.
        delay = SAVE_DELAY if self.hass.state is CoreState.running else SAVE_DELAY_LONG
        self._store.async_delay_save(self._data_to_save, delay)

    @callback
    @abstractmethod
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of registry to store in a file."""
