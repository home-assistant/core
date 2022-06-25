"""Classes shared among Wemo entities."""
from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging

from pywemo.exceptions import ActionException

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .wemo_device import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


class WemoEntity(CoordinatorEntity[DeviceCoordinator]):
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

    @property
    def name_suffix(self) -> str | None:
        """Suffix to append to the WeMo device name."""
        return self._name_suffix

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        wemo_name: str = self.wemo.name
        if suffix := self.name_suffix:
            return f"{wemo_name} {suffix}"
        return wemo_name

    @property
    def unique_id_suffix(self) -> str | None:
        """Suffix to append to the WeMo device's unique ID."""
        if self._unique_id_suffix is None and self.name_suffix is not None:
            return self.name_suffix.lower()
        return self._unique_id_suffix

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
        serial_number: str = self.wemo.serialnumber
        if suffix := self.unique_id_suffix:
            return f"{serial_number}_{suffix}"
        return serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return self._device_info

    @contextlib.contextmanager
    def _wemo_call_wrapper(self, message: str) -> Generator[None, None, None]:
        """Wrap calls to the device that change its state.

        1. Takes care of making available=False when communications with the
           device fails.
        2. Ensures all entities sharing the same coordinator are aware of
           updates to the device state.
        """
        try:
            yield
        except ActionException as err:
            _LOGGER.warning("Could not %s for %s (%s)", message, self.name, err)
            self.coordinator.last_exception = err
            self.coordinator.last_update_success = False  # Used for self.available.
        finally:
            self.hass.add_job(self.coordinator.async_update_listeners)


class WemoBinaryStateEntity(WemoEntity):
    """Base for devices that return on/off state via device.get_state()."""

    @property
    def is_on(self) -> bool:
        """Return true if the state is on."""
        return self.wemo.get_state() != 0
