"""Support for binary_sensor entities of the Evohome integration."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

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
from homeassistant.util.dt import parse_datetime

from .const import EVOHOME_DATA
from .coordinator import EvoDataUpdateCoordinator
from .entity import unique_zone_id


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create fault sensors for the active Evohome installation."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    entities: list[EvoFaultSensorBase] = [
        EvoGatewayFaultSensor(coordinator, tcs.gateway),
        EvoControllerFaultSensor(coordinator, tcs),
        *[EvoZoneFaultSensor(coordinator, z) for z in tcs.zones],
    ]

    if tcs.hotwater:
        entities.append(EvoDhwFaultSensor(coordinator, tcs.hotwater))

    async_add_entities(entities)


def _normalize_fault(fault: dict[str, Any]) -> dict[str, Any]:
    """Until library is updated to return snake_case, convert from PascalCase."""

    def _pascal_to_snake(val: str) -> str:
        s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", val)
        return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    return {
        "fault": _pascal_to_snake(fault["fault_type"]),
        "since": parse_datetime(fault["since"]),
    }


class EvoFaultSensorBase(
    CoordinatorEntity[EvoDataUpdateCoordinator], BinarySensorEntity
):
    """Base class for evohome fault sensors."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _evo_device: evo.ControlSystem | evo.HotWater | evo.Zone | evo.Gateway
    _evo_id_attr: str
    _evo_state_attr_names = ()

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.ControlSystem | evo.Zone | evo.HotWater | evo.Gateway,
    ) -> None:
        """Initialize the fault sensor."""
        super().__init__(coordinator, evo_device.id)

        self._attr_unique_id = f"{evo_device.id}_faults"
        self._evo_device = evo_device

    @property
    def is_on(self) -> bool:
        """Return true if the device currently reports active faults."""
        return bool(self._evo_device.active_faults)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return diagnostic details for all current faults."""
        faults = tuple(_normalize_fault(f) for f in self._evo_device.active_faults)  # type: ignore[arg-type]
        return {
            "fault_count": len(faults),
            "faults": faults,
        }


class EvoGatewayFaultSensor(EvoFaultSensorBase):
    """Fault sensor for a gateway."""

    _attr_name = "Gateway faults"

    _evo_device: evo.Gateway
    _evo_id_attr = "gateway_id"


class EvoControllerFaultSensor(EvoFaultSensorBase):
    """Fault sensor for a temperature control system."""

    _attr_name = "Controller faults"

    _evo_device: evo.ControlSystem
    _evo_id_attr = "system_id"


class EvoDhwFaultSensor(EvoFaultSensorBase):
    """Fault sensor for a DHW controller."""

    _attr_name = "DHW faults"

    _evo_device: evo.HotWater
    _evo_id_attr = "dhw_id"


class EvoZoneFaultSensor(EvoFaultSensorBase):
    """Fault sensor for a zone."""

    _evo_device: evo.Zone
    _evo_id_attr = "zone_id"

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
    ) -> None:
        """Initialize the zone faults binary sensor."""
        super().__init__(coordinator, evo_device)
        self._attr_unique_id = f"{unique_zone_id(evo_device)}_faults"

    @property
    def name(self) -> str:
        """Return the name, dynamically following any zone rename."""
        return f"{self._evo_device.name} faults"
