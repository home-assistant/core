"""Separate shared base classes for alarm entities and value-based sensors."""

from abc import abstractmethod
from typing import override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONF_ARM_HOME_ENABLED,
    CONF_INSTANT_ARM_AWAY,
    CONF_INSTANT_ARM_HOME,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    VISONIC_TRANSLATION_KEY,
)
from .coordinator import VisonicCoordinator
from .exceptions import VisonicException
from .utils import to_bool
from .visonic_data_types import VisonicConfigEntry, VisonicPanelData
from .visonic_types import PanelStateData


class AlarmBaseLogic(CoordinatorEntity[VisonicCoordinator]):
    """Base type for common functions between sensor and alarm_control_panel."""

    def __init__(self, entry: VisonicConfigEntry, identifier: str) -> None:
        """Initialize a Visonic security alarm."""
        vcd: VisonicPanelData = entry.runtime_data
        vc: VisonicCoordinator = vcd.coordinator
        if vc is None:
            raise VisonicException("Alarm has been given invalid coordinator", 101)
        super().__init__(coordinator=vc)
        self._entry = entry
        self._panel_ident = identifier
        self._attr_name = None
        self._name = self._panel_ident + "_main_panel"

        self._attr_unique_id = slugify(self._name)
        self._attr_should_poll = False
        self._attr_translation_key = VISONIC_TRANSLATION_KEY
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=MANUFACTURER,
        )
        self.panel_state_data: PanelStateData = PanelStateData()
        self.update_local(entry)
        self.coordinator.ive_been_created()

    def _update_panel_state(self) -> None:
        if not self.coordinator:
            LOGGER.warning(
                "Coordinator not ready for alarm panel %s yet it should be by now",
                self._name,
            )
            self.panel_state_data = PanelStateData()
            return
        self.panel_state_data = self.coordinator.get_panel_state()

    @abstractmethod
    def update_local(self, entry: VisonicConfigEntry) -> None:
        """Abstract base class for specific alarm and sensor devices to update."""

    @property
    def isarmhome(self) -> bool:  # noqa: D102
        return to_bool(self._entry.options.get(CONF_ARM_HOME_ENABLED, False))

    @property
    def isarmhomeinstant(self) -> bool:  # noqa: D102
        return to_bool(self._entry.options.get(CONF_INSTANT_ARM_HOME, False))

    @property
    def isarmawayinstant(self) -> bool:  # noqa: D102
        return to_bool(self._entry.options.get(CONF_INSTANT_ARM_AWAY, False))

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Get the state of the device."""
        self._update_panel_state()
        self.update_local(self._entry)
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available and that the coordinator has had an update."""
        return self._attr_available and self.coordinator.last_update_success
