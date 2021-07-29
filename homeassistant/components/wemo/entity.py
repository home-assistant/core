"""Classes shared among Wemo entities."""
from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging

from pywemo.exceptions import ActionException

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .wemo_device import DeviceWrapper

_LOGGER = logging.getLogger(__name__)


class WemoEntity(CoordinatorEntity):
    """Common methods for Wemo entities."""

    def __init__(self, device: DeviceWrapper) -> None:
        """Initialize the WeMo device."""
        super().__init__(device.coordinator)
        self.wemo = device.wemo
        self._device_info = device.device_info
        self._available = True

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self.wemo.name

    @property
    def available(self) -> bool:
        """Return true if the device is available."""
        return super().available and self._available

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
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
