"""Provide a common entity class for myUplink entities."""

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyUplinkConfigEntry, MyUplinkDataCoordinator


@callback
def async_add_device_entities(
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    entities_for_devices: Callable[[set[str]], Iterable[Entity]],
) -> None:
    """Add entities for the current devices, and for devices that show up later."""
    coordinator = config_entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        if not (new_devices := set(coordinator.data.devices) - known_devices):
            return
        known_devices.update(new_devices)
        async_add_entities(entities_for_devices(new_devices))

    _async_add_new_devices()
    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class MyUplinkEntity(CoordinatorEntity[MyUplinkDataCoordinator]):
    """Representation of myuplink entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator)

        # Internal properties
        self.device_id = device_id

        # Basic values
        self._attr_unique_id = f"{device_id}-{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_id)})


class MyUplinkSystemEntity(MyUplinkEntity):
    """Representation of a system bound entity."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        system_id: str,
        device_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.system_id = system_id

        # Basic values
        self._attr_unique_id = f"{system_id}-{unique_id_suffix}"
