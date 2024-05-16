"""Home Assistant extension for Syrupy."""

from __future__ import annotations

from contextlib import suppress
import dataclasses
from enum import IntFlag
from pathlib import Path
from typing import Any

import attr
import attrs
from syrupy.extensions.amber import AmberDataSerializer, AmberSnapshotExtension
from syrupy.location import PyTestLocation
from syrupy.types import (
    PropertyFilter,
    PropertyMatcher,
    PropertyPath,
    SerializableData,
    SerializedData,
)
import voluptuous as vol
import voluptuous_serialize

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import State
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)


class _ANY:
    """Represent any value."""

    def __repr__(self) -> str:
        return "<ANY>"


ANY = _ANY()

__all__ = ["HomeAssistantSnapshotExtension"]


class AreaRegistryEntrySnapshot(dict):
    """Tiny wrapper to represent an area registry entry in snapshots."""


class ConfigEntrySnapshot(dict):
    """Tiny wrapper to represent a config entry in snapshots."""


class DeviceRegistryEntrySnapshot(dict):
    """Tiny wrapper to represent a device registry entry in snapshots."""


class EntityRegistryEntrySnapshot(dict):
    """Tiny wrapper to represent an entity registry entry in snapshots."""


class FlowResultSnapshot(dict):
    """Tiny wrapper to represent a flow result in snapshots."""


class IssueRegistryItemSnapshot(dict):
    """Tiny wrapper to represent an entity registry entry in snapshots."""


class StateSnapshot(dict):
    """Tiny wrapper to represent an entity state in snapshots."""


class HomeAssistantSnapshotSerializer(AmberDataSerializer):
    """Home Assistant snapshot serializer for Syrupy.

    Handles special cases for Home Assistant data structures.
    """

    @classmethod
    def _serialize(
        cls,
        data: SerializableData,
        *,
        depth: int = 0,
        exclude: PropertyFilter | None = None,
        include: PropertyFilter | None = None,
        matcher: PropertyMatcher | None = None,
        path: PropertyPath = (),
        visited: set[Any] | None = None,
    ) -> SerializedData:
        """Pre-process data before serializing.

        This allows us to handle specific cases for Home Assistant data structures.
        """
        if isinstance(data, State):
            serializable_data = cls._serializable_state(data)
        elif isinstance(data, ar.AreaEntry):
            serializable_data = cls._serializable_area_registry_entry(data)
        elif isinstance(data, dr.DeviceEntry):
            serializable_data = cls._serializable_device_registry_entry(data)
        elif isinstance(data, er.RegistryEntry):
            serializable_data = cls._serializable_entity_registry_entry(data)
        elif isinstance(data, ir.IssueEntry):
            serializable_data = cls._serializable_issue_registry_entry(data)
        elif isinstance(data, dict) and "flow_id" in data and "handler" in data:
            serializable_data = cls._serializable_flow_result(data)
        elif isinstance(data, vol.Schema):
            serializable_data = voluptuous_serialize.convert(data)
        elif isinstance(data, ConfigEntry):
            serializable_data = cls._serializable_config_entry(data)
        elif dataclasses.is_dataclass(data):
            serializable_data = dataclasses.asdict(data)
        elif isinstance(data, IntFlag):
            # The repr of an enum.IntFlag has changed between Python 3.10 and 3.11
            # so we normalize it here.
            serializable_data = _IntFlagWrapper(data)
        else:
            serializable_data = data
            with suppress(TypeError):
                if attr.has(data):
                    serializable_data = attrs.asdict(data)

        return super()._serialize(
            serializable_data,
            depth=depth,
            exclude=exclude,
            include=include,
            matcher=matcher,
            path=path,
            visited=visited,
        )

    @classmethod
    def _serializable_area_registry_entry(cls, data: ar.AreaEntry) -> SerializableData:
        """Prepare a Home Assistant area registry entry for serialization."""
        serialized = AreaRegistryEntrySnapshot(attrs.asdict(data) | {"id": ANY})
        serialized.pop("_json_repr")
        return serialized

    @classmethod
    def _serializable_config_entry(cls, data: ConfigEntry) -> SerializableData:
        """Prepare a Home Assistant config entry for serialization."""
        return ConfigEntrySnapshot(data.as_dict() | {"entry_id": ANY})

    @classmethod
    def _serializable_device_registry_entry(
        cls, data: dr.DeviceEntry
    ) -> SerializableData:
        """Prepare a Home Assistant device registry entry for serialization."""
        serialized = DeviceRegistryEntrySnapshot(
            attrs.asdict(data)
            | {
                "config_entries": ANY,
                "id": ANY,
            }
        )
        if serialized["via_device_id"] is not None:
            serialized["via_device_id"] = ANY
        return serialized

    @classmethod
    def _serializable_entity_registry_entry(
        cls, data: er.RegistryEntry
    ) -> SerializableData:
        """Prepare a Home Assistant entity registry entry for serialization."""
        serialized = EntityRegistryEntrySnapshot(
            attrs.asdict(data)
            | {
                "config_entry_id": ANY,
                "device_id": ANY,
                "id": ANY,
                "options": {k: dict(v) for k, v in data.options.items()},
            }
        )
        serialized.pop("categories")
        return serialized

    @classmethod
    def _serializable_flow_result(cls, data: FlowResult) -> SerializableData:
        """Prepare a Home Assistant flow result for serialization."""
        return FlowResultSnapshot(data | {"flow_id": ANY})

    @classmethod
    def _serializable_issue_registry_entry(
        cls, data: ir.IssueEntry
    ) -> SerializableData:
        """Prepare a Home Assistant issue registry entry for serialization."""
        return IssueRegistryItemSnapshot(data.to_json() | {"created": ANY})

    @classmethod
    def _serializable_state(cls, data: State) -> SerializableData:
        """Prepare a Home Assistant State for serialization."""
        return StateSnapshot(
            data.as_dict()
            | {
                "context": ANY,
                "last_changed": ANY,
                "last_reported": ANY,
                "last_updated": ANY,
            }
        )


class _IntFlagWrapper:
    def __init__(self, flag: IntFlag) -> None:
        self._flag = flag

    def __repr__(self) -> str:
        # 3.10: <ClimateEntityFeature.SWING_MODE|PRESET_MODE|FAN_MODE|TARGET_TEMPERATURE: 57>
        # 3.11: <ClimateEntityFeature.TARGET_TEMPERATURE|FAN_MODE|PRESET_MODE|SWING_MODE: 57>
        # Syrupy: <ClimateEntityFeature: 57>
        return f"<{self._flag.__class__.__name__}: {self._flag.value}>"


class HomeAssistantSnapshotExtension(AmberSnapshotExtension):
    """Home Assistant extension for Syrupy."""

    VERSION = "1"
    """Current version of serialization format.

    Need to be bumped when we change the HomeAssistantSnapshotSerializer.
    """

    serializer_class: type[AmberDataSerializer] = HomeAssistantSnapshotSerializer

    @classmethod
    def dirname(cls, *, test_location: PyTestLocation) -> str:
        """Return the directory for the snapshot files.

        Syrupy, by default, uses the `__snapshosts__` directory in the same
        folder as the test file. For Home Assistant, this is changed to just
        `snapshots` in the same folder as the test file, to match our `fixtures`
        folder structure.
        """
        test_dir = Path(test_location.filepath).parent
        return str(test_dir.joinpath("snapshots"))
