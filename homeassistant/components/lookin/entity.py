"""The lookin integration entity."""
from __future__ import annotations

from abc import abstractmethod
import logging

from aiolookin import (
    POWER_CMD,
    POWER_OFF_CMD,
    POWER_ON_CMD,
    Climate,
    MeteoSensor,
    Remote,
)
from aiolookin.models import Device, UDPCommandType, UDPEvent

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import LookinDataUpdateCoordinator
from .models import LookinData

LOGGER = logging.getLogger(__name__)


def _lookin_device_to_device_info(lookin_device: Device, host: str) -> DeviceInfo:
    """Convert a lookin device into DeviceInfo."""
    return DeviceInfo(
        identifiers={(DOMAIN, lookin_device.id)},
        name=lookin_device.name,
        manufacturer="LOOKin",
        model=MODEL_NAMES[lookin_device.model],
        sw_version=lookin_device.firmware,
        configuration_url=f"http://{host}/device",
    )


def _lookin_controlled_device_to_device_info(
    lookin_device: Device, uuid: str, device: Climate | Remote, host: str
) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, uuid)},
        name=device.name,
        model=device.device_type,
        via_device=(DOMAIN, lookin_device.id),
        configuration_url=f"http://{host}/data/{uuid}",
    )


class LookinDeviceMixIn:
    """A mix in to set lookin attributes for the lookin device."""

    def _set_lookin_device_attrs(self, lookin_data: LookinData) -> None:
        """Set attrs for the lookin device."""
        self._lookin_device = lookin_data.lookin_device
        self._lookin_protocol = lookin_data.lookin_protocol
        self._lookin_udp_subs = lookin_data.lookin_udp_subs


class LookinDeviceCoordinatorEntity(
    LookinDeviceMixIn, CoordinatorEntity[LookinDataUpdateCoordinator[MeteoSensor]]
):
    """A lookin device entity on the device itself that uses the coordinator."""

    _attr_should_poll = False

    def __init__(self, lookin_data: LookinData) -> None:
        """Init the lookin device entity."""
        assert lookin_data.meteo_coordinator is not None
        super().__init__(lookin_data.meteo_coordinator)
        self._set_lookin_device_attrs(lookin_data)
        self._attr_device_info = _lookin_device_to_device_info(
            lookin_data.lookin_device, lookin_data.host
        )


class LookinEntityMixIn:
    """A mix in to set attributes for a lookin entity."""

    def _set_lookin_entity_attrs(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Set attrs for the device controlled via the lookin device."""
        self._device = device
        self._uuid = uuid
        self._meteo_coordinator = lookin_data.meteo_coordinator
        self._function_names = {function.name for function in self._device.functions}


class LookinCoordinatorEntity(
    LookinDeviceMixIn,
    LookinEntityMixIn,
    CoordinatorEntity[LookinDataUpdateCoordinator[Remote]],
):
    """A lookin device entity for an external device that uses the coordinator."""

    _attr_should_poll = False
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: LookinDataUpdateCoordinator[Remote],
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the base entity."""
        super().__init__(coordinator)
        self._set_lookin_device_attrs(lookin_data)
        self._set_lookin_entity_attrs(uuid, device, lookin_data)
        self._attr_device_info = _lookin_controlled_device_to_device_info(
            self._lookin_device, uuid, device, lookin_data.host
        )
        self._attr_unique_id = uuid
        self._attr_name = device.name

    async def _async_send_command(self, command: str, signal: str = "FF") -> None:
        """Send command from saved IR device."""
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=command, signal=signal
        )


class LookinPowerEntity(LookinCoordinatorEntity):
    """A Lookin entity that has a power on and power off command."""

    def __init__(
        self,
        coordinator: LookinDataUpdateCoordinator[Remote],
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the power entity."""
        super().__init__(coordinator, uuid, device, lookin_data)
        self._power_on_command: str = POWER_CMD
        self._power_off_command: str = POWER_CMD
        if POWER_ON_CMD in self._function_names:
            self._power_on_command = POWER_ON_CMD
        if POWER_OFF_CMD in self._function_names:
            self._power_off_command = POWER_OFF_CMD


class LookinPowerPushRemoteEntity(LookinPowerEntity):
    """A Lookin entity that has a power on and power off command with push updates."""

    def __init__(
        self,
        coordinator: LookinDataUpdateCoordinator[Remote],
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
    ) -> None:
        """Init the entity."""
        super().__init__(coordinator, uuid, device, lookin_data)
        self._update_from_status(self._remote.status)
        self._attr_name = self._remote.name

    @property
    def _remote(self) -> Remote:
        return self.coordinator.data

    @abstractmethod
    def _update_from_status(self, status: str) -> None:
        """Update properties from status."""

    def _async_push_update(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        self._update_from_status(event.value)
        self.coordinator.async_set_updated_data(self._remote)

    async def _async_push_update_device(self, event: UDPEvent) -> None:
        """Process an update pushed via UDP."""
        LOGGER.debug("Processing push message for %s: %s", self.entity_id, event)
        await self.coordinator.async_refresh()
        self._attr_name = self._remote.name

    async def async_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.ir,
                self._uuid,
                self._async_push_update,
            )
        )
        self.async_on_remove(
            self._lookin_udp_subs.subscribe_event(
                self._lookin_device.id,
                UDPCommandType.data,
                self._uuid,
                self._async_push_update_device,
            )
        )
