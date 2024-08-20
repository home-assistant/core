"""Qbus Config Entry wrapper."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL
from .qbus_queue import QbusStateQueue


class QbusEntry:
    """Qbus Config Entry wrapper."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Qbus Config Entry wrapper."""
        self._hass = hass
        self._config_entry = entry
        self._state_queue = QbusStateQueue(hass)

    @property
    def config_entry(self) -> ConfigEntry:
        """Return the Config Entry."""
        return self._config_entry

    @property
    def state_queue(self) -> QbusStateQueue:
        """Return the Qbus State Queue."""
        return self._state_queue

    @property
    def serial(self) -> str:
        """Return the controller serial."""
        return self._config_entry.data.get(CONF_SERIAL) or ""
