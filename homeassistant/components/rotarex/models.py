"""Data models for the Rotarex integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, kw_only=True)
class RotarexSyncData:
    """Represent a synchronization data entry."""

    synch_date: str
    level: float | None
    battery: float | None


@dataclass(frozen=True, kw_only=True)
class RotarexTank:
    """Represent a Rotarex tank."""

    guid: str
    name: str | None
    synch_datas: list[RotarexSyncData]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RotarexTank:
        """Create a RotarexTank from API dictionary data.

        This method transforms raw API responses into typed dataclass instances,
        handling nested SynchDatas conversion and providing a clean interface
        for the coordinator.
        """
        synch_datas = [
            RotarexSyncData(
                synch_date=sync["SynchDate"],
                level=sync.get("Level"),
                battery=sync.get("Battery"),
            )
            for sync in data["SynchDatas"]
        ]
        return cls(
            guid=data["Guid"],
            name=data.get("Name"),
            synch_datas=synch_datas,
        )
