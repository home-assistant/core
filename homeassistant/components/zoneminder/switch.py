"""Support for ZoneMinder switches."""
import logging
from typing import Callable, List, Optional

from zoneminder.monitor import Monitor, MonitorState

from homeassistant.components.switch import SwitchEntity
from homeassistant.components.zoneminder.common import get_config_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    zm_client = get_config_data(hass, config_entry).client

    switches = []
    for monitor in await hass.async_add_job(zm_client.get_monitors):
        for on_state in MonitorState:
            for off_state in MonitorState:
                if on_state == off_state:
                    continue

                print("BBBB")
                switches.append(
                    ZMSwitchMonitors(monitor, on_state, off_state, config_entry)
                )

    print("AAAAAA", switches)
    async_add_entities(switches, True)


class ZMSwitchMonitors(SwitchEntity):
    """Representation of a ZoneMinder switch."""

    icon = "mdi:record-rec"

    def __init__(
        self,
        monitor: Monitor,
        on_state: MonitorState,
        off_state: MonitorState,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        self._monitor = monitor
        self._on_state = on_state
        self._off_state = off_state
        self._config_entry = config_entry
        self._name = ZMSwitchMonitors.get_name(monitor.name, on_state, off_state)
        self._is_available = False
        self._state = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_{self._on_state.value}_{self._off_state.value}_state_switch"

    @property
    def name(self) -> Optional[str]:
        """Return the name of the switch."""
        return self._name

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    def update(self) -> None:
        """Update the switch value."""
        try:
            self._state = self._monitor.function == self._on_state
            self._is_available = True
        except Exception:  # pylint: disable=broad-except
            self._is_available = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        self._monitor.function = self._on_state

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self._monitor.function = self._off_state

    @staticmethod
    def get_name(
        monitor_name: str, on_state: MonitorState, off_state: MonitorState
    ) -> str:
        """Get a formatted name."""
        return f"Zoneminder {monitor_name} Switch {on_state.value} {off_state.value}"
