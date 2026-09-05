"""Support for Binary Sensor entities of the Evohome integration."""

from typing import override

import evohomeasync2 as evo
from evohomeasync2.const import SZ_FAULT_TYPE

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
from .entity import is_valid_zone, unique_zone_id


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the binary sensor platform for Evohome."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    entities: list[EvoBatterySensorBase] = [EvoTcsBatterySensor(coordinator, tcs)]

    entities.extend(
        EvoZoneBatterySensor(coordinator, z) for z in tcs.zones if is_valid_zone(z)
    )

    if tcs.hotwater:
        entities.append(EvoDhwBatterySensor(coordinator, tcs.hotwater))

    async_add_entities(entities)


class EvoBatterySensorBase(
    CoordinatorEntity[EvoDataUpdateCoordinator], BinarySensorEntity
):
    """Base for Evohome's low battery sensors."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _evo_device: evo.ControlSystem | evo.HotWater | evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.HotWater | evo.Zone,
    ) -> None:
        """Initialize an Evohome battery sensor."""
        super().__init__(coordinator, context=evo_device.id)

        self._evo_device = evo_device

        self._attr_unique_id = f"{evo_device.id}_{BinarySensorDeviceClass.BATTERY}"

    @property
    @override
    def is_on(self) -> bool:
        """Return True when the Evohome device has an active low-battery fault."""
        return any(
            str(f[SZ_FAULT_TYPE]).endswith("low_battery")
            for f in self._evo_device.active_faults
        )


class EvoTcsBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a system controller."""

    _evo_device: evo.ControlSystem

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows location renames)."""
        return f"{self._evo_device.location.name} controller battery"


class EvoDhwBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a DHW temperature sensor."""

    _evo_device: evo.HotWater

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows location renames)."""
        return f"{self._evo_device.location.name} DHW battery"


class EvoZoneBatterySensor(EvoBatterySensorBase):
    """Battery sensor for a heating zone."""

    _evo_device: evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
    ) -> None:
        """Initialize the zone actuator battery sensor."""
        super().__init__(coordinator, evo_device)

        self._attr_unique_id = (
            f"{unique_zone_id(evo_device)}_{BinarySensorDeviceClass.BATTERY}"
        )

    @property
    @override
    def name(self) -> str:
        """Return the entity name (follows zone renames)."""
        return f"{self._evo_device.name} battery"
