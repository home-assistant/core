"""Support for Škoda binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from skoda_public_api.models.enums import (
    LockState,
    OnOffState,
    OpenCloseState,
    VehicleCapability,
    YesNoState,
)
from skoda_public_api.models.vehicle_status import VehicleStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 0

_OPEN_CLOSE_MAP = {
    OpenCloseState.OPEN: True,
    OpenCloseState.CLOSED: False,
}

_ON_OFF_MAP = {
    OnOffState.ON: True,
    OnOffState.OFF: False,
}

_UNLOCKED_MAP = {
    LockState.UNLOCKED: True,
    LockState.LOCKED: False,
}

_NOT_LOCKED_MAP = {
    YesNoState.NO: True,
    YesNoState.YES: False,
}


@dataclass(frozen=True, kw_only=True)
class SkodaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Škoda binary sensor entity."""

    is_on_fn: Callable[[VehicleStatus], bool | None]
    required_capabilities: frozenset[VehicleCapability] = frozenset(
        {VehicleCapability.STATUS}
    )


BINARY_SENSOR_TYPES: tuple[SkodaBinarySensorEntityDescription, ...] = (
    SkodaBinarySensorEntityDescription(
        key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
        is_on_fn=lambda status: (
            _UNLOCKED_MAP.get(status.overall.reliable_lock_status)
            if status.overall.reliable_lock_status is not None
            else _NOT_LOCKED_MAP.get(status.overall.locked)
        ),
    ),
    SkodaBinarySensorEntityDescription(
        key="doors",
        translation_key="doors",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=lambda status: _OPEN_CLOSE_MAP.get(status.overall.doors),
    ),
    SkodaBinarySensorEntityDescription(
        key="windows",
        translation_key="windows",
        device_class=BinarySensorDeviceClass.WINDOW,
        is_on_fn=lambda status: _OPEN_CLOSE_MAP.get(status.overall.windows),
    ),
    SkodaBinarySensorEntityDescription(
        key="sunroof",
        translation_key="sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        required_capabilities=frozenset(
            {VehicleCapability.STATUS, VehicleCapability.SUNROOF}
        ),
        is_on_fn=lambda status: _OPEN_CLOSE_MAP.get(status.detail.sunroof),
    ),
    SkodaBinarySensorEntityDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=lambda status: _OPEN_CLOSE_MAP.get(status.detail.trunk),
    ),
    SkodaBinarySensorEntityDescription(
        key="bonnet",
        translation_key="bonnet",
        device_class=BinarySensorDeviceClass.OPENING,
        is_on_fn=lambda status: _OPEN_CLOSE_MAP.get(status.detail.bonnet),
    ),
    SkodaBinarySensorEntityDescription(
        key="lights",
        translation_key="lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        is_on_fn=lambda status: _ON_OFF_MAP.get(status.overall.lights),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator
    capabilities = coordinator.data.vehicle_response.supported_capabilities()

    async_add_entities(
        SkodaBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
        if description.required_capabilities <= capabilities
    )


class SkodaBinarySensor(SkodaEntity, BinarySensorEntity):
    """Škoda binary sensor entity, driven by its entity description."""

    entity_description: SkodaBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        if (status := self.open_api_vehicle.status) is None:
            return None
        return self.entity_description.is_on_fn(status)
