"""Support for VeSync time entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.time import TimeEntity, TimeEntityDescription, time
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_air_fryer
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VeSyncTimeEntityDescription(TimeEntityDescription):
    """Class to describe a Vesync number entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool] = lambda _: True
    value_fn: Callable[[VeSyncBaseDevice], float]


TIME_DESCRIPTIONS: list[VeSyncTimeEntityDescription] = [
    VeSyncTimeEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        exists_fn=is_air_fryer,
        value_fn=lambda device: device.state.remaining_time,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time entities."""

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
    """Add time entities."""

    async_add_entities(
        VeSyncTimeEntity(dev, description, coordinator)
        for dev in devices
        for description in TIME_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncTimeEntity(VeSyncBaseEntity, TimeEntity):
    """A class to set numeric options on Vesync device."""

    entity_description: VeSyncTimeEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncTimeEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the VeSync time device."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    @property
    def native_value(self) -> time:
        """Return the value reported by the number."""
        return self.entity_description.value_fn(self.device)
