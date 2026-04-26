"""Support for binary_sensor entities of the Evohome integration."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import re

import evohomeasync2 as evo
from evohomeasync2.schemas import EvoActiveFaultResponseT

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

type EvoDevice = evo.Gateway | evo.ControlSystem | evo.HotWater | evo.Zone


# Evohome has four device types: gateway -> controller (TCS) -> DHW (optional), zones
_DEVICE_LABEL: dict[type[EvoDevice], str] = {
    evo.Gateway: "gateway",  # is stateless, except for fault sensors
    evo.ControlSystem: "system",
    evo.HotWater: "DHW",
    evo.Zone: "zone",
}

# Fault categories exposed per evohome device type (gateways have no battery)
_SUPPORTED_CATEGORIES: dict[type[EvoDevice], tuple[BinarySensorDeviceClass, ...]] = {
    evo.Gateway: (
        BinarySensorDeviceClass.CONNECTIVITY,
        BinarySensorDeviceClass.PROBLEM,
    ),
    evo.ControlSystem: (
        BinarySensorDeviceClass.BATTERY,
        BinarySensorDeviceClass.CONNECTIVITY,
        BinarySensorDeviceClass.PROBLEM,
    ),
    evo.Zone: (
        BinarySensorDeviceClass.BATTERY,
        BinarySensorDeviceClass.CONNECTIVITY,
        BinarySensorDeviceClass.PROBLEM,
    ),
    evo.HotWater: (
        BinarySensorDeviceClass.BATTERY,
        BinarySensorDeviceClass.CONNECTIVITY,
        BinarySensorDeviceClass.PROBLEM,
    ),
}

# Generally, we match by StrEnum suffix; otherwise (incl. "Failure" suffix) is PROBLEM
_FAULT_TYPE_SUFFIX_TO_CATEGORY: dict[str, BinarySensorDeviceClass] = {
    "CommunicationLost": BinarySensorDeviceClass.CONNECTIVITY,
    "LowBattery": BinarySensorDeviceClass.BATTERY,
}

# These are exceptions to above: here, the TCS cannot see its components
_FAULT_TYPE_TO_CATEGORY: dict[str, BinarySensorDeviceClass] = {
    "BoilerCommunicationLost": BinarySensorDeviceClass.PROBLEM,
    "ChValveCommunicationLost": BinarySensorDeviceClass.PROBLEM,
}

# The sensor state when a fault is present (connectivity is inverted)
_CATEGORY_TRUE_WHEN_FAULT: dict[BinarySensorDeviceClass, bool] = {
    BinarySensorDeviceClass.BATTERY: True,
    BinarySensorDeviceClass.CONNECTIVITY: False,
    BinarySensorDeviceClass.PROBLEM: True,
}

# Name fragments used to build entity names (zones can change their name)
_CATEGORY_LABEL: dict[BinarySensorDeviceClass, str] = {
    BinarySensorDeviceClass.CONNECTIVITY: "connection",
    BinarySensorDeviceClass.BATTERY: "battery",
    BinarySensorDeviceClass.PROBLEM: "fault",
}


async def async_setup_platform(
    hass: HomeAssistant,
    _: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Create fault binary sensors for the active Evohome installation."""

    if discovery_info is None:
        return

    coordinator = hass.data[EVOHOME_DATA].coordinator
    tcs = hass.data[EVOHOME_DATA].tcs

    evo_devices: list[EvoDevice] = [tcs.gateway, tcs, *tcs.zones]
    if tcs.hotwater:
        evo_devices.append(tcs.hotwater)

    async_add_entities(
        EvoZoneFaultSensor(coordinator, device, device_class)
        if isinstance(device, evo.Zone)
        else EvoFaultSensor(coordinator, device, device_class)
        for device in evo_devices
        for device_class in _SUPPORTED_CATEGORIES[type(device)]
    )


def _pascal_to_snake(val: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", val)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _normalize_fault(fault: EvoActiveFaultResponseT) -> dict[str, datetime | str]:
    """Convert a library fault into a pythonic dictionary."""

    # Doing this here (rather than in the library) allows exposing faults now
    # without blocking on a library release, while avoiding a future breaking
    # change to attribute keys/values.

    return {
        "fault": _pascal_to_snake(fault["fault_type"]),
        "since": parse_datetime(fault["since"], raise_on_error=True),
    }  # raise_on_error is only for mypy typing


def _category_of_fault(fault_type: str) -> BinarySensorDeviceClass:
    """Return the category a fault_type belongs to."""
    if category := _FAULT_TYPE_TO_CATEGORY.get(fault_type):
        return category
    for suffix, category in _FAULT_TYPE_SUFFIX_TO_CATEGORY.items():
        if fault_type.endswith(suffix):
            return category
    return BinarySensorDeviceClass.PROBLEM


def _faults_of_category(
    faults: Iterable[EvoActiveFaultResponseT], device_class: BinarySensorDeviceClass
) -> list[EvoActiveFaultResponseT]:
    return [f for f in faults if _category_of_fault(f["fault_type"]) is device_class]


def _effective_faults(
    device: EvoDevice, device_class: BinarySensorDeviceClass
) -> list[EvoActiveFaultResponseT]:
    """Return faults for a device, propagating connectivity faults from ancestors.

    The vendor API only reports communication lost on the parent; children may appear
    fault-free although they are unreachable. For CONNECTIVITY sensors we walk up
    the hierarchy so that the TCS/zone/DHW sensors reflect the true situation.
    """

    own_fault = _faults_of_category(device.active_faults, device_class)
    if device_class is not BinarySensorDeviceClass.CONNECTIVITY:
        return own_fault

    ancestors: list[EvoDevice] = []
    if isinstance(device, evo.Zone | evo.HotWater):
        ancestors = [device.tcs, device.tcs.gateway]
    elif isinstance(device, evo.ControlSystem):
        ancestors = [device.gateway]

    inherited_faults = [
        f
        for ancestor in ancestors
        for f in _faults_of_category(ancestor.active_faults, device_class)
    ]
    return own_fault + inherited_faults


class EvoFaultSensor(CoordinatorEntity[EvoDataUpdateCoordinator], BinarySensorEntity):
    """Binary sensor exposing one category of Evohome faults for one device."""

    _attr_device_class: BinarySensorDeviceClass
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    _evo_device: EvoDevice

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: EvoDevice,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the fault sensor."""
        super().__init__(coordinator, context=evo_device.id)

        self._evo_device = evo_device

        self._attr_device_class = device_class
        self._attr_name = (
            f"{evo_device.location.name} {_DEVICE_LABEL[type(evo_device)]} "
            f"{_CATEGORY_LABEL[device_class]}"
        )
        self._attr_unique_id = f"{evo_device.id}_{device_class}"

    @property
    def is_on(self) -> bool:
        """Return whether this category currently has any active fault."""

        effective_faults = _effective_faults(self._evo_device, self._attr_device_class)
        if _CATEGORY_TRUE_WHEN_FAULT[self._attr_device_class]:
            return bool(effective_faults)
        return not bool(effective_faults)

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, datetime | str]]]:
        """Return the faults in this category with their start timestamps."""

        effective_faults = _effective_faults(self._evo_device, self._attr_device_class)
        return {"faults": [_normalize_fault(f) for f in effective_faults]}


class EvoZoneFaultSensor(EvoFaultSensor):
    """Binary sensor exposing one category of Evohome faults for one device."""

    _evo_device: evo.Zone

    def __init__(
        self,
        coordinator: EvoDataUpdateCoordinator,
        evo_device: evo.Zone,
        device_class: BinarySensorDeviceClass,
    ) -> None:
        """Initialize the fault sensor."""
        super().__init__(coordinator, evo_device, device_class)

        self._attr_unique_id = f"{unique_zone_id(evo_device)}_{device_class}"

    @property
    def name(self) -> str:
        """Return the entity name (follows zone renames)."""
        return f"{self._evo_device.name} {_CATEGORY_LABEL[self._attr_device_class]}"
