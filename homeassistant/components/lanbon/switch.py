"""Switch entities from LOIP components with type=switch."""

from typing import Any, override

from aiolanbon import LanbonError
from aiolanbon.models import Component, Device, DeviceSnapshot

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
        self._attr_unique_id = f"{device_id}_{component_id}"
        info = coordinator.info
        model = info.model if info else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=model,
            name=(info.model or MANUFACTURER) if info else MANUFACTURER,
        )
        self._sync_name()

    def _pair(self):
        snap = self.coordinator.data
        if snap is None:
            return None, None
        device = snap.device(self._device_id)
        if device is None:
            return None, None
        return device, device.component(self._component_id)

    def _sync_name(self) -> None:
        _device, component = self._pair()
        if component is not None:
            self._attr_name = component.name or self._component_id

    @property
    @override
    def available(self) -> bool:
        """Return True when the device and component are online and enabled."""
        device, component = self._pair()
        return bool(
            super().available
            and self.coordinator.last_update_success
            and device
            and device.online
            and component
            and component.enabled
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the on/off state."""
        _device, component = self._pair()
        if component is None:
            return None
        return bool(component.state.get("on"))

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_on(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_on(False)

    async def _set_on(self, on: bool) -> None:
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
