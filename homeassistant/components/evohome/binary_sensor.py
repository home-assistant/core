"""Support for binary_sensor entities of the Evohome integration."""

from typing import override

import evohomeasync2 as evo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import unique_zone_id

type EvoDevice = evo.ControlSystem | evo.HotWater | evo.Zone


def _has_battery_fault(device: EvoDevice) -> bool:
    """Return True if the device has an active low-battery fault."""
    return any(
        str(f["fault_type"]).endswith("low_battery") for f in device.active_faults
    )


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create battery binary sensors for the active Evohome installation."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    entities: list[EvoBatterySensorBase] = [EvoTcsBatterySensor(coordinator, tcs)]

    entities.extend(EvoZoneBatterySensor(coordinator, z) for z in tcs.zones)

    if tcs.hotwater:
        entities.append(EvoDhwBatterySensor(coordinator, tcs.hotwater))

    async_add_entities(entities)


class EvoBatterySensorBase(
    CoordinatorEntity[EvoDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor exposing low-battery faults for one Evohome device."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _evo_device: EvoDevice

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: EvoDevice,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, context=evo_device.id)

        self._evo_device = evo_device

        self._attr_unique_id = f"{evo_device.id}_{BinarySensorDeviceClass.BATTERY}"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when there is an active low-battery fault."""
        return _has_battery_fault(self._evo_device)


class EvoTcsBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a system controller."""

    _evo_device: evo.ControlSystem

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows location renames)."""
        return f"{self._evo_device.location.name} controller"


class EvoDhwBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a DHW temperature sensor."""

    _evo_device: evo.HotWater

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows location renames)."""
        return f"{self._evo_device.location.name} DHW"


class EvoZoneBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a heating zone."""

    _evo_device: evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
    ) -> None:
        """Initialize the zone battery sensor."""
        super().__init__(coordinator, evo_device)

        self._attr_unique_id = (
            f"{unique_zone_id(evo_device)}_{BinarySensorDeviceClass.BATTERY}"
        )

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows zone renames)."""
        return self._evo_device.name
