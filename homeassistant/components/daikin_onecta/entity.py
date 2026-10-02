"""Entity classes for the Daikin Onecta integration."""

import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity_descriptions import SWITCH_DESCRIPTIONS

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

_LOGGER = logging.getLogger(__name__)


class DaikinSwitch(CoordinatorEntity[OnectaDataUpdateCoordinator], ToggleEntity):
    """Represent a switchable Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        management_point_type: str,
        value: str,
    ) -> None:
        """Initialize the switch from a device characteristic."""
        _LOGGER.info("DaikinSwitch '%s' '%s'", management_point_type, value)
        super().__init__(coordinator)
        self._device = device
        self._embedded_id = embedded_id
        self._management_point_type = management_point_type
        self._value = value
        self._switch_state = self.sensor_value()
        self._attr_has_entity_name = True
        self.entity_description = SWITCH_DESCRIPTIONS.get(
            value, SwitchEntityDescription(key=value)
        )
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._value}"
        mpt = management_point_type[0].upper() + management_point_type[1:]
        assert self._device.ha_device_id is not None
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + embedded_id)},
            "name": self._device.name + " " + mpt,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, embedded_id)

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._switch_state = self.sensor_value()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        return self._switch_state == "on"

    def sensor_value(self) -> str:
        """Return the state of the switch."""
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            point.characteristic(self._value) if point is not None else None
        )
        return characteristic.value if characteristic is not None else ""

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        if not self.is_on and await self._device.patch(
            self._device.id, self._embedded_id, self._value, "", "on"
        ):
            self._switch_state = "on"
            self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        if self.is_on and await self._device.patch(
            self._device.id, self._embedded_id, self._value, "", "off"
        ):
            self._switch_state = "off"
            self.async_write_ha_state()
