"""Support for VeSync numeric entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import override

from pyvesync.base_devices import VeSyncHumidifier
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_humidifier
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VeSyncNumberEntityDescription(NumberEntityDescription):
    """Class to describe a Vesync number entity."""

    exists_fn: Callable[[VeSyncHumidifier], bool] = lambda _: True
    value_fn: Callable[[VeSyncHumidifier], float | None]
    native_min_value_fn: Callable[[VeSyncHumidifier], float]
    native_max_value_fn: Callable[[VeSyncHumidifier], float]
    set_value_fn: Callable[[VeSyncHumidifier, float], Awaitable[bool]]


NUMBER_DESCRIPTIONS: list[VeSyncNumberEntityDescription] = [
    VeSyncNumberEntityDescription(
        key="mist_level",
        translation_key="mist_level",
        native_min_value_fn=lambda device: min(device.mist_levels),
        native_max_value_fn=lambda device: max(device.mist_levels),
        native_step=1,
        mode=NumberMode.SLIDER,
        set_value_fn=lambda device, value: device.set_mist_level(int(value)),
        value_fn=lambda device: device.state.mist_virtual_level,
    ),
    VeSyncNumberEntityDescription(
        key="warm_mist_level",
        translation_key="warm_mist_level",
        native_min_value_fn=lambda device: min(device.warm_mist_levels),
        native_max_value_fn=lambda device: max(device.warm_mist_levels),
        native_step=1,
        mode=NumberMode.SLIDER,
        exists_fn=lambda device: device.supports_warm_mist,
        set_value_fn=lambda device, value: device.set_warm_level(int(value)),
        value_fn=lambda device: device.state.warm_mist_level or 0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add number entities."""

    async_add_entities(
        VeSyncNumberEntity(dev, description, coordinator)
        for dev in devices
        if is_humidifier(dev)
        for description in NUMBER_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncNumberEntity(VeSyncBaseEntity[VeSyncHumidifier], NumberEntity):
    """A class to set numeric options on Vesync device."""

    entity_description: VeSyncNumberEntityDescription

    def __init__(
        self,
        device: VeSyncHumidifier,
        description: VeSyncNumberEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync number device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self.device)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_min_value_fn(self.device)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the value reported by the number."""
        return self.entity_description.native_max_value_fn(self.device)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not await self.entity_description.set_value_fn(self.device, value):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Failed to set value.")
        self.async_write_ha_state()
