"""Support for SwitchBee entity."""
import logging
from typing import Generic, TypeVar, cast

from switchbee import SWITCHBEE_BRAND
from switchbee.device import DeviceType, SwitchBeeBaseDevice

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBeeCoordinator

_DeviceTypeT = TypeVar("_DeviceTypeT", bound=SwitchBeeBaseDevice)


_LOGGER = logging.getLogger(__name__)


class SwitchBeeEntity(CoordinatorEntity[SwitchBeeCoordinator], Generic[_DeviceTypeT]):
    """Representation of a Switchbee entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        device: _DeviceTypeT,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_name = device.name
        self._attr_unique_id = f"{coordinator.unique_id}-{device.id}"


class SwitchBeeDeviceEntity(SwitchBeeEntity[_DeviceTypeT]):
    """Representation of a Switchbee device entity."""

    def __init__(
        self,
        device: _DeviceTypeT,
        coordinator: SwitchBeeCoordinator,
    ) -> None:
        """Initialize the Switchbee device."""
        super().__init__(device, coordinator)
        self._is_online: bool = True
        identifier = (
            device.id if device.type == DeviceType.Thermostat else device.unit_id
        )
        self._attr_device_info = DeviceInfo(
            name=device.zone,
            identifiers={
                (
                    DOMAIN,
                    f"{identifier}-{coordinator.unique_id}",
                )
            },
            manufacturer=SWITCHBEE_BRAND,
            model=coordinator.api.module_display(device.unit_id),
            suggested_area=device.zone,
            via_device=(
                DOMAIN,
                f"{coordinator.api.name} ({coordinator.api.unique_id})",
            ),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_online and super().available

    def _check_if_became_offline(self) -> None:
        """Check if the device was online (now offline), log message and mark it as Unavailable."""

        if self._is_online:
            _LOGGER.warning(
                (
                    "%s device is not responding, check the status in the SwitchBee"
                    " mobile app"
                ),
                self.name,
            )
            self._is_online = False

    def _check_if_became_online(self) -> None:
        """Check if the device was offline (now online) and bring it back."""
        if not self._is_online:
            _LOGGER.info(
                "%s device is now responding",
                self.name,
            )
            self._is_online = True

    def _get_coordinator_device(self) -> _DeviceTypeT:
        return cast(_DeviceTypeT, self.coordinator.data[self._device.id])
