"""Test the NZBGet sensors."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.nzbget.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    UnitOfDataRate,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import ENTRY_OPTIONS, init_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("nzbget_api")
async def test_sensors(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test the creation and values of the sensors."""
    now = dt_util.utcnow().replace(microsecond=0)
    with patch("homeassistant.components.nzbget.sensor.utcnow", return_value=now):
        entry = await init_integration(hass)

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
            "1.25",
            UnitOfDataRate.MEGABYTES_PER_SECOND,
            SensorDeviceClass.DATA_RATE,
        ),
        "download_paused": ("DownloadPaused", "False", None, None),
        "speed": (
            "DownloadRate",
            "2.5",
            UnitOfDataRate.MEGABYTES_PER_SECOND,
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
            "1.0",
            UnitOfDataRate.MEGABYTES_PER_SECOND,
            SensorDeviceClass.DATA_RATE,
        ),
    }

    for sensor_id, data in sensors.items():
        entity_entry = entity_registry.async_get(f"sensor.nzbgettest_{sensor_id}")
        assert entity_entry
        assert entity_entry.original_device_class == data[3]
        assert entity_entry.unique_id == f"{entry.entry_id}_{data[0]}"

        state = hass.states.get(f"sensor.nzbgettest_{sensor_id}")
        assert state
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == data[2]
        assert state.state == data[1]


@pytest.mark.usefixtures("nzbget_api")
async def test_sensor_name_from_entry_title(hass: HomeAssistant) -> None:
    """Test sensors are named from the entry title when no legacy name is stored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="10.10.10.30",
        data={
            CONF_HOST: "10.10.10.30",
            CONF_PASSWORD: "",
            CONF_PORT: 6789,
            CONF_SSL: False,
            CONF_USERNAME: "",
            CONF_VERIFY_SSL: False,
        },
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.10_10_10_30_speed")
    assert state
    assert state.name == "10.10.10.30 Speed"
