"""Test the NZBGet sensors."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfDataRate,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_sensors(hass: HomeAssistant, nzbget_api) -> None:
    """Test the creation and values of the sensors."""
    now = dt_util.utcnow().replace(microsecond=0)
    with patch("homeassistant.components.nzbget.sensor.utcnow", return_value=now):
        entry = await init_integration(hass)

    registry = er.async_get(hass)

    uptime = now - timedelta(seconds=600)

    sensors = {
        "article_cache": (
            "ArticleCacheMB",
            "64",
            UnitOfInformation.MEGABYTES,
            SensorDeviceClass.DATA_SIZE,
        ),
        "average_speed": (
            "AverageDownloadRate",
            "1250000",
            UnitOfDataRate.BYTES_PER_SECOND,
            SensorDeviceClass.DATA_RATE,
        ),
        "download_paused": ("DownloadPaused", "False", None, None),
        "speed": (
            "DownloadRate",
            "2500000",
            UnitOfDataRate.BYTES_PER_SECOND,
            SensorDeviceClass.DATA_RATE,
        ),
        "size": (
            "DownloadedSizeMB",
            "256",
            UnitOfInformation.MEGABYTES,
            SensorDeviceClass.DATA_SIZE,
        ),
        "disk_free": (
            "FreeDiskSpaceMB",
            "1024",
            UnitOfInformation.MEGABYTES,
            SensorDeviceClass.DATA_SIZE,
        ),
        "post_processing_jobs": ("PostJobCount", "2", "Jobs", None),
        "post_processing_paused": ("PostPaused", "False", None, None),
        "queue_size": (
            "RemainingSizeMB",
            "512",
            UnitOfInformation.MEGABYTES,
            SensorDeviceClass.DATA_SIZE,
        ),
        "uptime": ("UpTimeSec", uptime.isoformat(), None, SensorDeviceClass.TIMESTAMP),
        "speed_limit": (
            "DownloadLimit",
            "1000000",
            UnitOfDataRate.BYTES_PER_SECOND,
            SensorDeviceClass.DATA_RATE,
        ),
    }

    for sensor_id, data in sensors.items():
        entity_entry = registry.async_get(f"sensor.nzbgettest_{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == f"{entry.entry_id}_{data[0]}"

        state = hass.states.get(f"sensor.nzbgettest_{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]
