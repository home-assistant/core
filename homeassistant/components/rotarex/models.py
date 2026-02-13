"""Data models for the Rotarex integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RotarexSyncData:
    """Represent a synchronization data entry."""

    synch_date: str
    level: float | None
    battery: float | None


@dataclass
class RotarexTank:
    """Represent a Rotarex tank."""

    guid: str
    name: str | None
    synch_datas: list[RotarexSyncData]

    @classmethod
    def from_dict(cls, data: dict) -> RotarexTank:
        """Create a RotarexTank from API dictionary data."""
        synch_datas = [
            RotarexSyncData(
                synch_date=sync.get("SynchDate", ""),
                level=sync.get("Level"),
                battery=sync.get("Battery"),
            )
            for sync in data.get("SynchDatas", [])
        ]
        return cls(
            guid=data["Guid"],
            name=data.get("Name"),
            synch_datas=synch_datas,
        )
