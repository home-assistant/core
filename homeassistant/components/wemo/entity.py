"""Classes shared among Wemo entities."""
from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging

from pywemo.exceptions import ActionException

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .wemo_device import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


class WemoEntity(CoordinatorEntity):
    """Common methods for Wemo entities."""

    # Most pyWeMo devices are associated with a single Home Assistant entity. When
    # that is not the case, name_suffix & unique_id_suffix can be used to provide
    # names and unique ids for additional Home Assistant entities.
    _name_suffix: str | None = None
    _unique_id_suffix: str | None = None

    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the WeMo device."""
        super().__init__(coordinator)
        self.wemo = coordinator.wemo
        self._device_info = coordinator.device_info
        self._available = True

    @property
    def name_suffix(self):
        """Suffix to append to the WeMo device name."""
        return self._name_suffix

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        suffix = self.name_suffix
        if suffix:
            return f"{self.wemo.name} {suffix}"
        return self.wemo.name

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        return super().available and self._available

    @property
    def unique_id_suffix(self):
        """Suffix to append to the WeMo device's unique ID."""
        if self._unique_id_suffix is None and self.name_suffix is not None:
            return self._name_suffix.lower()
        return self._unique_id_suffix

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
        suffix = self.unique_id_suffix
        if suffix:
            return f"{self.wemo.serialnumber}_{suffix}"
        return self.wemo.serialnumber

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._available = True
        super()._handle_coordinator_update()

    @contextlib.contextmanager
    def _wemo_exception_handler(self, message: str) -> Generator[None, None, None]:
        """Wrap device calls to set `_available` when wemo exceptions happen."""
        try:
            yield
        except ActionException as err:
            _LOGGER.warning("Could not %s for %s (%s)", message, self.name, err)
            self._available = False
