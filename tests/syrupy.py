"""Compatibility imports for the Home Assistant pytest helpers."""

# ruff: noqa: PLC0414

from pytest_homeassistant.syrupy import (
    _ANY as _ANY,
    _INTERNAL_DEVICE_ENTRY_ATTRIBUTES as _INTERNAL_DEVICE_ENTRY_ATTRIBUTES,
    ANY as ANY,
    AmberDataSerializer as AmberDataSerializer,
    AmberSnapshotExtension as AmberSnapshotExtension,
    Any as Any,
    AreaRegistryEntrySnapshot as AreaRegistryEntrySnapshot,
    ConfigEntry as ConfigEntry,
    ConfigEntrySnapshot as ConfigEntrySnapshot,
    DeviceRegistryEntrySnapshot as DeviceRegistryEntrySnapshot,
    EntityRegistryEntrySnapshot as EntityRegistryEntrySnapshot,
    FlowResult as FlowResult,
    FlowResultSnapshot as FlowResultSnapshot,
    HomeAssistantSnapshotExtension as HomeAssistantSnapshotExtension,
    HomeAssistantSnapshotSerializer as HomeAssistantSnapshotSerializer,
    IntFlag as IntFlag,
    IssueRegistryItemSnapshot as IssueRegistryItemSnapshot,
    Path as Path,
    PropertyFilter as PropertyFilter,
    PropertyMatcher as PropertyMatcher,
    PropertyPath as PropertyPath,
    PyTestLocation as PyTestLocation,
    SerializableData as SerializableData,
    State as State,
    StateSnapshot as StateSnapshot,
    _IntFlagWrapper as _IntFlagWrapper,
    ar as ar,
    attr as attr,
    attrs as attrs,
    dataclasses as dataclasses,
    dr as dr,
    er as er,
    ir as ir,
    probatio as probatio,
    suppress as suppress,
)

__all__ = ["HomeAssistantSnapshotExtension"]
