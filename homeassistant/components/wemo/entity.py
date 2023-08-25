"""Classes shared among Wemo entities."""
from __future__ import annotations

from collections.abc import Generator
import contextlib
import logging

from pywemo.exceptions import ActionException

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .wemo_device import DeviceCoordinator

_LOGGER = logging.getLogger(__name__)


class WemoEntity(CoordinatorEntity[DeviceCoordinator]):
    """Common methods for Wemo entities."""

    _attr_has_entity_name = True
    # Most pyWeMo devices are associated with a single Home Assistant entity. When
    # that is not the case, unique_id_suffix can be used to provide names and unique
    # ids for additional Home Assistant entities.
    _unique_id_suffix: str | None = None

    def __init__(self, coordinator: DeviceCoordinator) -> None:
        """Initialize the WeMo device."""
        super().__init__(coordinator)
        self.wemo = coordinator.wemo
        self._device_info = coordinator.device_info

    @property
    def unique_id_suffix(self) -> str | None:
        """Suffix to append to the WeMo device's unique ID."""
        return self._unique_id_suffix

    @property
    def unique_id(self) -> str:
        """Return the id of this WeMo device."""
        serial_number: str = self.wemo.serial_number
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
