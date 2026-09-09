"""Persist source-window progress for Tesla Fleet energy statistics."""

from datetime import datetime
from typing import TypedDict

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticDataTimestamp,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER


class EnergyHistoryCheckpoint(TypedDict):
    """A replay boundary and the recorder data that must exist before using it."""

    start: float
    statistics: dict[str, StatisticDataTimestamp]


class EnergyHistoryStore(Store[EnergyHistoryCheckpoint]):
    """Keep source progress without inventing readings for absent fields."""

    def __init__(self, hass: HomeAssistant, entry_id: str, site_id: str | int) -> None:
        """Create a store scoped to this entry and energy site."""
        super().__init__(
            hass,
            1,
            f"{DOMAIN}.{entry_id}.{int(site_id)}.energy_history",
            private=True,
            atomic_writes=True,
        )

    async def async_get_start(
        self, last_stats: dict[str, StatisticData]
    ) -> datetime | None:
        """Return the saved boundary only if its imports are present in recorder."""
        if (checkpoint := await self.async_load()) is None:
            return None
        start = dt_util.utc_from_timestamp(checkpoint["start"])
        expected = checkpoint["statistics"]
        if not all(
            (actual := last_stats.get(statistic_id)) is not None
            and (
                actual["start"].timestamp() > stat["start_ts"]
                or (
                    actual["start"].timestamp() == stat["start_ts"]
                    and actual["state"] == stat["state"]
                    and actual["sum"] == stat["sum"]
                )
            )
            for statistic_id, stat in expected.items()
        ) or any(
            statistic_id not in expected and stat["start"] < start
            for statistic_id, stat in last_stats.items()
        ):
            LOGGER.debug(
                "Ignoring energy history checkpoint that does not match recorder"
            )
            return None
        return start

    async def async_set_start(
        self, start: datetime, last_stats: dict[str, StatisticData]
    ) -> None:
        """Save source coverage with anchors for detecting uncommitted imports."""
        await self.async_save(
            {
                "start": start.timestamp(),
                "statistics": {
                    statistic_id: StatisticDataTimestamp(
                        start_ts=stat["start"].timestamp(),
                        state=stat["state"],
                        sum=stat["sum"],
                    )
                    for statistic_id, stat in last_stats.items()
                },
            }
        )
