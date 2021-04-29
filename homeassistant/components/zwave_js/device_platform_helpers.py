"""Helper classes for device platform discovery."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

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

    resolved: bool = field(default=False, init=False)

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

    def resolve(self, value: ZwaveValue) -> None:
        """
        Resolve helper class data for a discovered value.

        Not to be overwritten by subclasses.
        """
        if self.resolved:
            raise Exception("Helper data has already been resolved.")
        self._resolve(value)
        self.resolved = True

    @property
    def value_ids_to_watch(self) -> set[str]:
        """
        Return list of all Value IDs resolved by helper that should be watched.

        Not to be overwritten by subclasses.
        """
        if not self.resolved:
            raise TypeError(
                "Helper data must first be resolved using resolve() command."
            )

        return {val.value_id for val in self._values_to_watch if val}

    def _resolve(self, value: ZwaveValue) -> None:
        """
        Resolve helper class data for a discovered value.

        Can optionally be implemented by subclasses if input data needs to be
        transformed once discovered Value is available.
        """
        pass

    @property
    def _values_to_watch(self) -> Iterable[ZwaveValue]:
        """
        Return list of all ZwaveValues resolved by helper that should be watched.

        Should be implemented by subclasses only if there are values to watch.
        """
        return []


@dataclass
class DynamicCurrentTempClimateHelper(BaseDevicePlatformHelper):
    """Helper class for Z-Wave JS Climate entities that have dynamic current temps."""

    id_lookup_table: dict[str | int, ZwaveValueID]
    id_dependent_value: ZwaveValueID
    lookup_table: dict[str | int, ZwaveValue | None] = {}
    dependent_value: ZwaveValue | None = None

    def _resolve(self, value: ZwaveValue) -> None:
        """Resolve helper class data for a discovered value."""
        for key in self.id_lookup_table:
            self.lookup_table[key] = self._get_value_from_id(
                value.node, self.id_lookup_table[key]
            )

        self.dependent_value = self._get_value_from_id(
            value.node, self.id_dependent_value
        )

    @property
    def _values_to_watch(self) -> Iterable[ZwaveValue]:
        """Return list of all ZwaveValues resolved by helper that should be watched."""
        return [*self.lookup_table.values(), self.dependent_value]
