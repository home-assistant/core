"""Switch entities from LOIP components with type=switch."""

import re
from typing import Any, override

from aiolanbon import LanbonError
from aiolanbon.models import Component, Device, DeviceSnapshot

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LanbonConfigEntry
from .const import DOMAIN, MANUFACTURER
from .coordinator import LanbonCoordinator

PARALLEL_UPDATES = 1


def _is_switch_component(component: Component) -> bool:
    """Return True when LOIP declares type=switch and set_on."""
    return component.type == "switch" and "set_on" in component.commands


def _iter_switch_components(
    snapshot: DeviceSnapshot | None,
) -> list[tuple[Device, Component]]:
    """Return switch components from a snapshot."""
    if snapshot is None:
        return []
    rows: list[tuple[Device, Component]] = []
    for device in snapshot.devices:
        rows.extend(
            (device, component)
            for component in device.components
            if _is_switch_component(component)
        )
    return rows


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LanbonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities from the LOIP snapshot."""
    coordinator = entry.runtime_data
    entities = [
        LanbonSwitch(coordinator, device.id, component.id)
        for device, component in _iter_switch_components(coordinator.data)
    ]
    async_add_entities(entities)


class LanbonSwitch(CoordinatorEntity[LanbonCoordinator], SwitchEntity):
    """A LOIP switch component."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LanbonCoordinator, device_id: str, component_id: str
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._component_id = component_id
        self._gateway_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{self._gateway_id}_{device_id}_{component_id}"
        self._device_identifier = (
            device_id
            if device_id == self._gateway_id
            else f"{self._gateway_id}_{device_id}"
        )
        self._sync_name()

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Use the snapshot device identity, not the gateway info for every child."""
        device = self._device
        snap = self.coordinator.data
        info = self.coordinator.info
        gateway_id = (info.gateway_id if info else "") or (
            snap.gateway_id if snap else ""
        )
        if device is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self._device_identifier)},
                manufacturer=MANUFACTURER,
            )
        gateway = dr.async_get(self.coordinator.hass).async_get_device_by_identifier(
            (DOMAIN, gateway_id), self.coordinator.config_entry.entry_id
        )
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_identifier)},
            connections=(
                {(dr.CONNECTION_NETWORK_MAC, device.id)}
                if re.fullmatch(r"[0-9a-f]{12}", device.id)
                else set()
            ),
            manufacturer=device.manufacturer or MANUFACTURER,
            model=device.model or None,
            name=device.name or device.model or MANUFACTURER,
            sw_version=device.firmware_version
            or (info.firmware_version if info and device.id == gateway_id else None),
            hw_version=device.hardware_version
            or (info.hardware_version if info and device.id == gateway_id else None),
        )
        if gateway and device.id != gateway_id:
            device_info["via_device_id"] = gateway.id
        return device_info

    @property
    def _device(self) -> Device | None:
        """Return the device from the latest snapshot."""
        if (snapshot := self.coordinator.data) is None:
            return None
        return snapshot.device(self._device_id)

    @property
    def _component(self) -> Component | None:
        """Return the component from the latest snapshot."""
        if (device := self._device) is None:
            return None
        return device.component(self._component_id)

    def _sync_name(self) -> None:
        component = self._component
        if component is not None:
            self._attr_name = component.name or self._component_id

    @property
    @override
    def available(self) -> bool:
        """Return True when the device and component are online and enabled."""
        device, component = self._device, self._component
        return bool(
            super().available
            and self.coordinator.gateway_verified
            and device
            and device.online
            and component
            and component.enabled
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the on/off state."""
        component = self._component
        if component is None:
            return None
        value = component.state.get("on")
        if isinstance(value, bool):
            return value
        return None

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_on(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_on(False)

    async def _set_on(self, on: bool) -> None:
        if not self.coordinator.gateway_verified:
            raise HomeAssistantError("Gateway identity has not been verified")
        try:
            await self.coordinator.client.send_command(
                self._device_id,
                self._component_id,
                "set_on",
                {"on": on},
            )
        except LanbonError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()

    @override
    def _handle_coordinator_update(self) -> None:
        """Refresh the entity name from the latest snapshot."""
        self._sync_name()
        super()._handle_coordinator_update()
