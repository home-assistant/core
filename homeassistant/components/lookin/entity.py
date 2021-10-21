"""The lookin integration entity."""
from __future__ import annotations

from aiolookin import POWER_CMD, POWER_OFF_CMD, POWER_ON_CMD, Climate, Remote
from aiolookin.models import Device

from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .models import LookinData


def _lookin_device_to_device_info(lookin_device: Device) -> DeviceInfo:
    """Convert a lookin device into DeviceInfo."""
    return DeviceInfo(
        identifiers={(DOMAIN, lookin_device.id)},
        name=lookin_device.name,
        manufacturer="LOOKin",
        model="LOOKin Remote2",
        sw_version=lookin_device.firmware,
    )


class LookinDeviceEntity(Entity):
    """A lookin device entity on the device itself."""

    _attr_should_poll = False

    def __init__(self, lookin_data: LookinData) -> None:
        """Init the lookin device entity."""
        self._lookin_device = lookin_data.lookin_device
        self._lookin_protocol = lookin_data.lookin_protocol
        self._lookin_udp_subs = lookin_data.lookin_udp_subs
        self._attr_device_info = _lookin_device_to_device_info(
            lookin_data.lookin_device
        )


class LookinDeviceCoordinatorEntity(LookinDeviceEntity, CoordinatorEntity):
    """A lookin device entity on the device itself that uses the coordinator."""

    def __init__(self, lookin_data: LookinData) -> None:
        """Init the lookin device entity."""
        super().__init__(lookin_data)
        CoordinatorEntity.__init__(self, lookin_data.meteo_coordinator)


class LookinEntity(Entity):
    """A base class for lookin entities."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the base entity."""
        self._device = device
        self._uuid = uuid
        self._lookin_device = lookin_data.lookin_device
        self._lookin_protocol = lookin_data.lookin_protocol
        self._lookin_udp_subs = lookin_data.lookin_udp_subs
        self._meteo_coordinator = lookin_data.meteo_coordinator
        self._function_names = {function.name for function in self._device.functions}
        self._attr_unique_id = uuid
        self._attr_name = self._device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._uuid)},
            name=self._device.name,
            model=self._device.device_type,
            via_device=(DOMAIN, self._lookin_device.id),
        )

    async def _async_send_command(self, command: str) -> None:
        """Send command from saved IR device."""
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=command, signal="FF"
        )


class LookinCoordinatorEntity(LookinEntity, CoordinatorEntity):
    """A lookin device entity for an external device that uses the coordinator."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the lookin device entity."""
        super().__init__(uuid, device, lookin_data)
        CoordinatorEntity.__init__(self, coordinator)


class LookinPowerEntity(LookinEntity):
    """A Lookin entity that has a power on and power off command."""

    def __init__(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the power entity."""
        super().__init__(uuid, device, lookin_data)
        self._power_on_command: str = POWER_CMD
        self._power_off_command: str = POWER_CMD
        if POWER_ON_CMD in self._function_names:
            self._power_on_command = POWER_ON_CMD
        if POWER_OFF_CMD in self._function_names:
            self._power_off_command = POWER_OFF_CMD
