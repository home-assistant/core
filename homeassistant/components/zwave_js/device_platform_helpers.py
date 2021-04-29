"""Helper classes for device platform discovery."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from zwave_js_server.model.node import Node as ZwaveNode
from zwave_js_server.model.value import Value as ZwaveValue, get_value_id


@dataclass
class ZwaveValueID:
    """Class to represent a value ID."""

    property_: str | int
    command_class: int
    endpoint: int | None = None
    property_key: str | int | None = None


@dataclass
class BaseDevicePlatformHelper:
    """Base class for device platform helpers."""

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """
        Resolve helper class data for a discovered value.

        Can optionally be implemented by subclasses if input data needs to be
        transformed once discovered Value is available.
        """
        return {}

    def values_to_watch(self, resolved_data: dict[str, Any]) -> Iterable[ZwaveValue]:
        """
        Return list of all ZwaveValues resolved by helper that should be watched.

        Should be implemented by subclasses only if there are values to watch.
        """
        return []

    def value_ids_to_watch(self, resolved_data: dict[str, Any]) -> set[str]:
        """
        Return list of all Value IDs resolved by helper that should be watched.

        Not to be overwritten by subclasses.
        """
        return {val.value_id for val in self.values_to_watch(resolved_data) if val}

    def _get_value_from_id(
        self, node: ZwaveNode, value_id_obj: ZwaveValueID
    ) -> ZwaveValue | None:
        """Get a ZwaveValue from a node using a ZwaveValueDict."""
        value_id = get_value_id(
            node,
            value_id_obj.command_class,
            value_id_obj.property_,
            endpoint=value_id_obj.endpoint,
            property_key=value_id_obj.property_key,
        )
        return node.values.get(value_id)


@dataclass
class DynamicCurrentTempClimateHelper(BaseDevicePlatformHelper):
    """Helper class for Z-Wave JS Climate entities that have dynamic current temps."""

    lookup_table: dict[str | int, ZwaveValueID]
    dependent_value: ZwaveValueID

    def resolve_data(self, value: ZwaveValue) -> dict[str, Any]:
        """Resolve helper class data for a discovered value."""
        data: dict[str, Any] = {
            "lookup_table": {},
            "dependent_value": self._get_value_from_id(
                value.node, self.dependent_value
            ),
        }
        for key in self.lookup_table:
            data["lookup_table"][key] = self._get_value_from_id(
                value.node, self.lookup_table[key]
            )

        return data

    def values_to_watch(self, resolved_data: dict[str, Any]) -> Iterable[ZwaveValue]:
        """Return list of all ZwaveValues resolved by helper that should be watched."""
        return [
            *resolved_data["lookup_table"].values(),
            resolved_data["dependent_value"],
        ]
