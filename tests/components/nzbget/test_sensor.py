"""Test the NZBGet sensors."""
from datetime import timedelta

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    DATA_MEGABYTES,
    DATA_RATE_MEGABYTES_PER_SECOND,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.util import dt as dt_util

from . import init_integration

from tests.async_mock import patch


async def test_sensors(hass) -> None:
    """Test the creation and values of the sensors."""
    now = dt_util.utcnow().replace(microsecond=0)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        entry = await init_integration(hass)

    registry = await hass.helpers.entity_registry.async_get_registry()

    uptime = now + timedelta(seconds=600)

    sensors = {
        "article_cache": (64, DATA_MEGABYTES, None),
        "average_download_rate": (512, DATA_RATE_MEGABYTES_PER_SECOND, None),
        "download_paused": (4, None, None),
        "download_rate": (1000, DATA_RATE_MEGABYTES_PER_SECOND, None),
        "download_size": (256, DATA_MEGABYTES, None),
        "free_disk_space": (1024, DATA_MEGABYTES, None),
        "post_job_count": (2, "Jobs", None),
        "post_paused": (4, None, None),
        "remaining_size": (512, DATA_MEGABYTES, None),
        "uptime": (uptime.isoformat(), None, DEVICE_CLASS_TIMESTAMP),
    }

    for (sensor_id, data) in sensors.items():
        entity = registry.async_get(f"sensor.nzbgettest_{sensor_id}")
        assert entity
        assert entity.device_class == data[2]
        assert entity.unique_id == f"{entry.entry_id}_{sensor_id}"

        state = hass.states.get(f"sensor.nzbgettest_{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[1]
        assert state.state == data[0]
