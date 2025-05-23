"""AVM FRITZ!Tools entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import AvmWrapper, FritzDevice


class FritzDeviceBase(CoordinatorEntity[AvmWrapper]):
    """Entity base class for a device connected to a FRITZ!Box device."""

    def __init__(self, avm_wrapper: AvmWrapper, device: FritzDevice) -> None:
        """Initialize a FRITZ!Box device."""
        super().__init__(avm_wrapper)
        self._avm_wrapper = avm_wrapper
        self._mac: str = device.mac_address
        self._name: str = device.hostname or DEFAULT_DEVICE_NAME
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac_address)}
        )

    @property
    def name(self) -> str:
        """Return device name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        if self._mac:
            return self._avm_wrapper.devices[self._mac].ip_address
        return None

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        if self._mac:
            return self._avm_wrapper.devices[self._mac].hostname
        return None

    async def async_process_update(self) -> None:
        """Update device."""
        raise NotImplementedError

    async def async_on_demand_update(self) -> None:
        """Update state."""
        await self.async_process_update()
        self.async_write_ha_state()


class FritzBoxBaseEntity:
    """Fritz host entity base class."""

    def __init__(self, avm_wrapper: AvmWrapper, device_name: str) -> None:
        """Init device info class."""
        self._avm_wrapper = avm_wrapper
        self._device_name = device_name
        self.mac_address = self._avm_wrapper.mac

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self.mac_address)},
            identifiers={(DOMAIN, self._avm_wrapper.unique_id)},
        )


@dataclass(frozen=True, kw_only=True)
class FritzEntityDescription(EntityDescription):
    """Fritz entity base description."""

    value_fn: Callable[[FritzStatus, Any], Any] | None


class FritzBoxBaseCoordinatorEntity(CoordinatorEntity[AvmWrapper]):
    """Fritz host coordinator entity base class."""

    entity_description: FritzEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        avm_wrapper: AvmWrapper,
        device_name: str,
        description: FritzEntityDescription,
    ) -> None:
        """Init device info class."""
        super().__init__(avm_wrapper)
        self.entity_description = description
        self._device_name = device_name
        self._attr_unique_id = f"{avm_wrapper.unique_id}-{description.key}"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        if self.entity_description.value_fn is not None:
            self.async_on_remove(
                await self.coordinator.async_register_entity_updates(
                    self.entity_description.key, self.entity_description.value_fn
                )
            )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return DeviceInfo(
            configuration_url=f"http://{self.coordinator.host}",
            connections={(dr.CONNECTION_NETWORK_MAC, self.coordinator.mac)},
            identifiers={(DOMAIN, self.coordinator.unique_id)},
            manufacturer="AVM",
            model=self.coordinator.model,
            name=self._device_name,
            sw_version=self.coordinator.current_firmware,
        )
