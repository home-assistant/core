"""The lookin integration entity."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .aiolookin import POWER_CMD, POWER_OFF_CMD, POWER_ON_CMD, Climate, Remote
from .const import DOMAIN
from .models import LookinData


class LookinEntity(Entity):
    """A base class for lookin entities."""

    def __init__(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the base entity."""
        self._device = device
        self._uuid = uuid
        self.coordinator = lookin_data.meteo_coordinator
        self._lookin_device = lookin_data.lookin_device
        self._lookin_protocol = lookin_data.lookin_protocol
        self._lookin_udp_subs = lookin_data.lookin_udp_subs
        self._attr_unique_id = uuid

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def available(self) -> bool:
        """Return true if the device is polling successfully."""
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the remote."""
        return {
            "identifiers": {(DOMAIN, self._uuid)},
            "name": self._device.name,
            "model": self._device.device_type,
            "via_device": (DOMAIN, self._lookin_device.id),
        }


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
        function_names = {function.name for function in self._device.functions}
        if POWER_ON_CMD in function_names:
            self._power_on_command = POWER_ON_CMD
        if POWER_OFF_CMD in function_names:
            self._power_off_command = POWER_OFF_CMD
