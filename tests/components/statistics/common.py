"""Test helpers for the statistics integration."""
from datetime import datetime, timedelta

from homeassistant.components import recorder
from homeassistant.components.recorder.db_schema import Statistics
from homeassistant.core import HomeAssistant

from tests.components.recorder.common import async_wait_recording_done


async def generate_statistics(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    count: int,
    start_value: float = 0.0,
) -> None:
    """Generate LTS data."""

    imported_stats = [
        {
            "start": (start + timedelta(hours=i)),
            "max": start_value + i * 2,
            "mean": start_value + i,
            "min": -(start_value + count * 2) + i * 2,
            "sum": start_value + i,
        }
        for i in range(0, count)
    ]

    imported_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": None,
        "source": "recorder",
        "statistic_id": entity_id,
        "unit_of_measurement": "°C",
    }

    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats,
        Statistics,
    )
    await async_wait_recording_done(hass)
