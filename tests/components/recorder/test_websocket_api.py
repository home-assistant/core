"""The tests for sensor recorder platform."""
import datetime
from datetime import timedelta
from statistics import fmean
import threading
from unittest.mock import ANY, patch

from freezegun import freeze_time
import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import Statistics, StatisticsShortTerm
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    get_metadata,
    list_statistic_ids,
)
from homeassistant.components.recorder.websocket_api import UNIT_SCHEMA
from homeassistant.components.sensor import UNIT_CONVERTERS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .common import (
    async_recorder_block_till_done,
    async_wait_recording_done,
    create_engine_test,
    do_adhoc_statistics,
    statistics_during_period,
)

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator

DISTANCE_SENSOR_FT_ATTRIBUTES = {
    "device_class": "distance",
    "state_class": "measurement",
    "unit_of_measurement": "ft",
}
DISTANCE_SENSOR_M_ATTRIBUTES = {
    "device_class": "distance",
    "state_class": "measurement",
    "unit_of_measurement": "m",
}
ENERGY_SENSOR_KWH_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "total",
    "unit_of_measurement": "kWh",
}
ENERGY_SENSOR_WH_ATTRIBUTES = {
    "device_class": "energy",
    "state_class": "total",
    "unit_of_measurement": "Wh",
}
GAS_SENSOR_FT3_ATTRIBUTES = {
    "device_class": "gas",
    "state_class": "total",
    "unit_of_measurement": "ft³",
}
GAS_SENSOR_M3_ATTRIBUTES = {
    "device_class": "gas",
    "state_class": "total",
    "unit_of_measurement": "m³",
}
POWER_SENSOR_KW_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "kW",
}
POWER_SENSOR_W_ATTRIBUTES = {
    "device_class": "power",
    "state_class": "measurement",
    "unit_of_measurement": "W",
}
PRESSURE_SENSOR_HPA_ATTRIBUTES = {
    "device_class": "pressure",
    "state_class": "measurement",
    "unit_of_measurement": "hPa",
}
PRESSURE_SENSOR_PA_ATTRIBUTES = {
    "device_class": "pressure",
    "state_class": "measurement",
    "unit_of_measurement": "Pa",
}
SPEED_SENSOR_KPH_ATTRIBUTES = {
    "device_class": "speed",
    "state_class": "measurement",
    "unit_of_measurement": "km/h",
}
SPEED_SENSOR_MPH_ATTRIBUTES = {
    "device_class": "speed",
    "state_class": "measurement",
    "unit_of_measurement": "mph",
}
TEMPERATURE_SENSOR_C_ATTRIBUTES = {
    "device_class": "temperature",
    "state_class": "measurement",
    "unit_of_measurement": "°C",
}
TEMPERATURE_SENSOR_F_ATTRIBUTES = {
    "device_class": "temperature",
    "state_class": "measurement",
    "unit_of_measurement": "°F",
}
VOLUME_SENSOR_FT3_ATTRIBUTES = {
    "device_class": "volume",
    "state_class": "measurement",
    "unit_of_measurement": "ft³",
}
VOLUME_SENSOR_M3_ATTRIBUTES = {
    "device_class": "volume",
    "state_class": "measurement",
    "unit_of_measurement": "m³",
}
VOLUME_SENSOR_FT3_ATTRIBUTES_TOTAL = {
    "device_class": "volume",
    "state_class": "total",
    "unit_of_measurement": "ft³",
}
VOLUME_SENSOR_M3_ATTRIBUTES_TOTAL = {
    "device_class": "volume",
    "state_class": "total",
    "unit_of_measurement": "m³",
}


def test_converters_align_with_sensor() -> None:
    """Ensure UNIT_SCHEMA is aligned with sensor UNIT_CONVERTERS."""
    for converter in UNIT_CONVERTERS.values():
        assert converter.UNIT_CLASS in UNIT_SCHEMA.schema

    for unit_class in UNIT_SCHEMA.schema:
        assert any(c for c in UNIT_CONVERTERS.values() if unit_class == c.UNIT_CLASS)


async def test_statistics_during_period(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    hass.config.units = US_CUSTOMARY_SYSTEM
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", 10, attributes=POWER_SENSOR_KW_ATTRIBUTES)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(10),
                "min": pytest.approx(10),
                "max": pytest.approx(10),
                "last_reset": None,
            }
        ]
    }

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "types": ["mean"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(10),
            }
        ]
    }


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
@pytest.mark.parametrize("offset", (0, 1, 2))
async def test_statistic_during_period(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    offset,
) -> None:
    """Test statistic_during_period."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    now = dt_util.utcnow()

    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    zero = now
    start = zero.replace(minute=offset * 5, second=0, microsecond=0) + timedelta(
        hours=-3
    )

    imported_stats_5min = [
        {
            "start": (start + timedelta(minutes=5 * i)),
            "max": i * 2,
            "mean": i,
            "min": -76 + i * 2,
            "sum": i,
        }
        for i in range(0, 39)
    ]
    imported_stats = []
    slice_end = 12 - offset
    imported_stats.append(
        {
            "start": imported_stats_5min[0]["start"].replace(minute=0),
            "max": max(stat["max"] for stat in imported_stats_5min[0:slice_end]),
            "mean": fmean(stat["mean"] for stat in imported_stats_5min[0:slice_end]),
            "min": min(stat["min"] for stat in imported_stats_5min[0:slice_end]),
            "sum": imported_stats_5min[slice_end - 1]["sum"],
        }
    )
    for i in range(0, 2):
        slice_start = i * 12 + (12 - offset)
        slice_end = (i + 1) * 12 + (12 - offset)
        assert imported_stats_5min[slice_start]["start"].minute == 0
        imported_stats.append(
            {
                "start": imported_stats_5min[slice_start]["start"],
                "max": max(
                    stat["max"] for stat in imported_stats_5min[slice_start:slice_end]
                ),
                "mean": fmean(
                    stat["mean"] for stat in imported_stats_5min[slice_start:slice_end]
                ),
                "min": min(
                    stat["min"] for stat in imported_stats_5min[slice_start:slice_end]
                ),
                "sum": imported_stats_5min[slice_end - 1]["sum"],
            }
        )

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.test",
        "unit_of_measurement": "kWh",
    }

    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats,
        Statistics,
    )
    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats_5min,
        StatisticsShortTerm,
    )
    await async_wait_recording_done(hass)

    # No data for this period yet
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "start_time": now.isoformat(),
                "end_time": now.isoformat(),
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": None,
        "mean": None,
        "min": None,
        "change": None,
    }

    # This should include imported_statistics_5min[:]
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:]),
        "min": min(stat["min"] for stat in imported_stats_5min[:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"],
    }

    # This should also include imported_statistics_5min[:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T04:00:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    end_time = (
        dt_util.parse_datetime("2022-10-21T07:15:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:]),
        "min": min(stat["min"] for stat in imported_stats_5min[:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"],
    }

    # This should also include imported_statistics_5min[:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T04:00:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    end_time = (
        dt_util.parse_datetime("2022-10-21T08:20:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:]),
        "min": min(stat["min"] for stat in imported_stats_5min[:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"],
    }

    # This should include imported_statistics_5min[26:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T06:10:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[26]["start"].isoformat() == start_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "start_time": start_time,
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[26:]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[26:]),
        "min": min(stat["min"] for stat in imported_stats_5min[26:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[25]["sum"],
    }

    # This should also include imported_statistics_5min[26:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T06:09:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "start_time": start_time,
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[26:]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[26:]),
        "min": min(stat["min"] for stat in imported_stats_5min[26:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[25]["sum"],
    }

    # This should include imported_statistics_5min[:26]
    end_time = (
        dt_util.parse_datetime("2022-10-21T06:10:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[26]["start"].isoformat() == end_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "end_time": end_time,
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:26]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:26]),
        "min": min(stat["min"] for stat in imported_stats_5min[:26]),
        "change": imported_stats_5min[25]["sum"] - 0,
    }

    # This should include imported_statistics_5min[26:32] (less than a full hour)
    start_time = (
        dt_util.parse_datetime("2022-10-21T06:10:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[26]["start"].isoformat() == start_time
    end_time = (
        dt_util.parse_datetime("2022-10-21T06:40:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[32]["start"].isoformat() == end_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[26:32]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[26:32]),
        "min": min(stat["min"] for stat in imported_stats_5min[26:32]),
        "change": imported_stats_5min[31]["sum"] - imported_stats_5min[25]["sum"],
    }

    # This should include imported_statistics[2:] + imported_statistics_5min[36:]
    start_time = "2022-10-21T06:00:00+00:00"
    assert imported_stats_5min[24 - offset]["start"].isoformat() == start_time
    assert imported_stats[2]["start"].isoformat() == start_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "fixed_period": {
                "start_time": start_time,
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[24 - offset :]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[24 - offset :]),
        "min": min(stat["min"] for stat in imported_stats_5min[24 - offset :]),
        "change": imported_stats_5min[-1]["sum"]
        - imported_stats_5min[23 - offset]["sum"],
    }

    # This should also include imported_statistics[2:] + imported_statistics_5min[36:]
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "rolling_window": {
                "duration": {"hours": 1, "minutes": 25},
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[24 - offset :]),
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[24 - offset :]),
        "min": min(stat["min"] for stat in imported_stats_5min[24 - offset :]),
        "change": imported_stats_5min[-1]["sum"]
        - imported_stats_5min[23 - offset]["sum"],
    }

    # This should include imported_statistics[2:3]
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "rolling_window": {
                "duration": {"hours": 1},
                "offset": {"minutes": -25},
            },
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    slice_start = 24 - offset
    slice_end = 36 - offset
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[slice_start:slice_end]),
        "mean": fmean(
            stat["mean"] for stat in imported_stats_5min[slice_start:slice_end]
        ),
        "min": min(stat["min"] for stat in imported_stats_5min[slice_start:slice_end]),
        "change": imported_stats_5min[slice_end - 1]["sum"]
        - imported_stats_5min[slice_start - 1]["sum"],
    }

    # Test we can get only selected types
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "types": ["max", "change"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]),
        "change": imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"],
    }

    # Test we can convert units
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "units": {"energy": "MWh"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]) / 1000,
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:]) / 1000,
        "min": min(stat["min"] for stat in imported_stats_5min[:]) / 1000,
        "change": (imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"])
        / 1000,
    }

    # Test we can automatically convert units
    hass.states.async_set("sensor.test", None, attributes=ENERGY_SENSOR_WH_ATTRIBUTES)
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats_5min[:]) * 1000,
        "mean": fmean(stat["mean"] for stat in imported_stats_5min[:]) * 1000,
        "min": min(stat["min"] for stat in imported_stats_5min[:]) * 1000,
        "change": (imported_stats_5min[-1]["sum"] - imported_stats_5min[0]["sum"])
        * 1000,
    }


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
async def test_statistic_during_period_hole(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistic_during_period when there are holes in the data."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    now = dt_util.utcnow()

    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    zero = now
    start = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=-18)

    imported_stats = [
        {
            "start": (start + timedelta(hours=3 * i)),
            "max": i * 2,
            "mean": i,
            "min": -76 + i * 2,
            "sum": i,
        }
        for i in range(0, 6)
    ]

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.test",
        "unit_of_measurement": "kWh",
    }

    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats,
        Statistics,
    )
    await async_wait_recording_done(hass)

    # This should include imported_stats[:]
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats[:]),
        "min": min(stat["min"] for stat in imported_stats[:]),
        "change": imported_stats[-1]["sum"] - imported_stats[0]["sum"],
    }

    # This should also include imported_stats[:]
    start_time = "2022-10-20T13:00:00+00:00"
    end_time = "2022-10-21T05:00:00+00:00"
    assert imported_stats[0]["start"].isoformat() == start_time
    assert imported_stats[-1]["start"].isoformat() < end_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats[:]),
        "min": min(stat["min"] for stat in imported_stats[:]),
        "change": imported_stats[-1]["sum"] - imported_stats[0]["sum"],
    }

    # This should also include imported_stats[:]
    start_time = "2022-10-20T13:00:00+00:00"
    end_time = "2022-10-21T08:20:00+00:00"
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats[:]),
        "mean": fmean(stat["mean"] for stat in imported_stats[:]),
        "min": min(stat["min"] for stat in imported_stats[:]),
        "change": imported_stats[-1]["sum"] - imported_stats[0]["sum"],
    }

    # This should include imported_stats[1:4]
    start_time = "2022-10-20T16:00:00+00:00"
    end_time = "2022-10-20T23:00:00+00:00"
    assert imported_stats[1]["start"].isoformat() == start_time
    assert imported_stats[3]["start"].isoformat() < end_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats[1:4]),
        "mean": fmean(stat["mean"] for stat in imported_stats[1:4]),
        "min": min(stat["min"] for stat in imported_stats[1:4]),
        "change": imported_stats[3]["sum"] - imported_stats[1]["sum"],
    }

    # This should also include imported_stats[1:4]
    start_time = "2022-10-20T15:00:00+00:00"
    end_time = "2022-10-21T00:00:00+00:00"
    assert imported_stats[1]["start"].isoformat() > start_time
    assert imported_stats[3]["start"].isoformat() < end_time
    await client.send_json(
        {
            "id": next_id(),
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "fixed_period": {
                "start_time": start_time,
                "end_time": end_time,
            },
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "max": max(stat["max"] for stat in imported_stats[1:4]),
        "mean": fmean(stat["mean"] for stat in imported_stats[1:4]),
        "min": min(stat["min"] for stat in imported_stats[1:4]),
        "change": imported_stats[3]["sum"] - imported_stats[1]["sum"],
    }


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("calendar_period", "start_time", "end_time"),
    (
        (
            {"period": "hour"},
            "2022-10-21T07:00:00+00:00",
            "2022-10-21T08:00:00+00:00",
        ),
        (
            {"period": "hour", "offset": -1},
            "2022-10-21T06:00:00+00:00",
            "2022-10-21T07:00:00+00:00",
        ),
        (
            {"period": "day"},
            "2022-10-21T07:00:00+00:00",
            "2022-10-22T07:00:00+00:00",
        ),
        (
            {"period": "day", "offset": -1},
            "2022-10-20T07:00:00+00:00",
            "2022-10-21T07:00:00+00:00",
        ),
        (
            {"period": "week"},
            "2022-10-17T07:00:00+00:00",
            "2022-10-24T07:00:00+00:00",
        ),
        (
            {"period": "week", "offset": -1},
            "2022-10-10T07:00:00+00:00",
            "2022-10-17T07:00:00+00:00",
        ),
        (
            {"period": "month"},
            "2022-10-01T07:00:00+00:00",
            "2022-11-01T07:00:00+00:00",
        ),
        (
            {"period": "month", "offset": -1},
            "2022-09-01T07:00:00+00:00",
            "2022-10-01T07:00:00+00:00",
        ),
        (
            {"period": "year"},
            "2022-01-01T08:00:00+00:00",
            "2023-01-01T08:00:00+00:00",
        ),
        (
            {"period": "year", "offset": -1},
            "2021-01-01T08:00:00+00:00",
            "2022-01-01T08:00:00+00:00",
        ),
    ),
)
async def test_statistic_during_period_calendar(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    calendar_period,
    start_time,
    end_time,
) -> None:
    """Test statistic_during_period."""
    client = await hass_ws_client()

    # Try requesting data for the current hour
    with patch(
        "homeassistant.components.recorder.websocket_api.statistic_during_period",
        return_value={},
    ) as statistic_during_period:
        await client.send_json(
            {
                "id": 1,
                "type": "recorder/statistic_during_period",
                "calendar": calendar_period,
                "statistic_id": "sensor.test",
            }
        )
        response = await client.receive_json()
        statistic_during_period.assert_called_once_with(
            hass, ANY, ANY, "sensor.test", None, units=None
        )
        assert statistic_during_period.call_args[0][1].isoformat() == start_time
        assert statistic_during_period.call_args[0][2].isoformat() == end_time
        assert response["success"]


@pytest.mark.parametrize(
    ("attributes", "state", "value", "custom_units", "converted_value"),
    [
        (DISTANCE_SENSOR_M_ATTRIBUTES, 10, 10, {"distance": "cm"}, 1000),
        (DISTANCE_SENSOR_M_ATTRIBUTES, 10, 10, {"distance": "m"}, 10),
        (DISTANCE_SENSOR_M_ATTRIBUTES, 10, 10, {"distance": "in"}, 10 / 0.0254),
        (POWER_SENSOR_KW_ATTRIBUTES, 10, 10, {"power": "W"}, 10000),
        (POWER_SENSOR_KW_ATTRIBUTES, 10, 10, {"power": "kW"}, 10),
        (PRESSURE_SENSOR_HPA_ATTRIBUTES, 10, 10, {"pressure": "Pa"}, 1000),
        (PRESSURE_SENSOR_HPA_ATTRIBUTES, 10, 10, {"pressure": "hPa"}, 10),
        (PRESSURE_SENSOR_HPA_ATTRIBUTES, 10, 10, {"pressure": "psi"}, 1000 / 6894.757),
        (SPEED_SENSOR_KPH_ATTRIBUTES, 10, 10, {"speed": "m/s"}, 2.77778),
        (SPEED_SENSOR_KPH_ATTRIBUTES, 10, 10, {"speed": "km/h"}, 10),
        (SPEED_SENSOR_KPH_ATTRIBUTES, 10, 10, {"speed": "mph"}, 6.21371),
        (TEMPERATURE_SENSOR_C_ATTRIBUTES, 10, 10, {"temperature": "°C"}, 10),
        (TEMPERATURE_SENSOR_C_ATTRIBUTES, 10, 10, {"temperature": "°F"}, 50),
        (TEMPERATURE_SENSOR_C_ATTRIBUTES, 10, 10, {"temperature": "K"}, 283.15),
        (VOLUME_SENSOR_M3_ATTRIBUTES, 10, 10, {"volume": "m³"}, 10),
        (VOLUME_SENSOR_M3_ATTRIBUTES, 10, 10, {"volume": "ft³"}, 353.14666),
    ],
)
async def test_statistics_during_period_unit_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    state,
    value,
    custom_units,
    converted_value,
) -> None:
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    # Query in state unit
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(value),
                "min": pytest.approx(value),
                "max": pytest.approx(value),
                "last_reset": None,
            }
        ]
    }

    # Query in custom unit
    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "units": custom_units,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(converted_value),
                "min": pytest.approx(converted_value),
                "max": pytest.approx(converted_value),
                "last_reset": None,
            }
        ]
    }


@pytest.mark.parametrize(
    ("attributes", "state", "value", "custom_units", "converted_value"),
    [
        (ENERGY_SENSOR_KWH_ATTRIBUTES, 10, 10, {"energy": "kWh"}, 10),
        (ENERGY_SENSOR_KWH_ATTRIBUTES, 10, 10, {"energy": "MWh"}, 0.010),
        (ENERGY_SENSOR_KWH_ATTRIBUTES, 10, 10, {"energy": "Wh"}, 10000),
        (GAS_SENSOR_M3_ATTRIBUTES, 10, 10, {"volume": "m³"}, 10),
        (GAS_SENSOR_M3_ATTRIBUTES, 10, 10, {"volume": "ft³"}, 353.147),
        (VOLUME_SENSOR_M3_ATTRIBUTES_TOTAL, 10, 10, {"volume": "m³"}, 10),
        (VOLUME_SENSOR_M3_ATTRIBUTES_TOTAL, 10, 10, {"volume": "ft³"}, 353.147),
    ],
)
async def test_sum_statistics_during_period_unit_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    state,
    value,
    custom_units,
    converted_value,
) -> None:
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", 0, attributes=attributes)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    # Query in state unit
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "change": pytest.approx(value),
                "last_reset": None,
                "state": pytest.approx(value),
                "sum": pytest.approx(value),
            }
        ]
    }

    # Query in custom unit
    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "units": custom_units,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "change": pytest.approx(converted_value),
                "last_reset": None,
                "state": pytest.approx(converted_value),
                "sum": pytest.approx(converted_value),
            }
        ]
    }


@pytest.mark.parametrize(
    "custom_units",
    [
        {"distance": "L"},
        {"energy": "W"},
        {"power": "Pa"},
        {"pressure": "K"},
        {"temperature": "m³"},
        {"volume": "kWh"},
    ],
)
async def test_statistics_during_period_invalid_unit_conversion(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    custom_units,
) -> None:
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    # Query in state unit
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    # Query in custom unit
    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "units": custom_units,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_statistics_during_period_in_the_past(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period in the past."""
    hass.config.set_time_zone("UTC")
    now = dt_util.utcnow().replace()

    hass.config.units = US_CUSTOMARY_SYSTEM
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    past = now - timedelta(days=3)

    with freeze_time(past):
        hass.states.async_set("sensor.test", 10, attributes=POWER_SENSOR_KW_ATTRIBUTES)
        await async_wait_recording_done(hass)

    sensor_state = hass.states.get("sensor.test")
    assert sensor_state.last_updated == past

    stats_top_of_hour = past.replace(minute=0, second=0, microsecond=0)
    stats_start = past.replace(minute=55)
    do_adhoc_statistics(hass, start=stats_start)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "hour",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}

    past = now - timedelta(days=3, hours=1)
    await client.send_json(
        {
            "id": 3,
            "type": "recorder/statistics_during_period",
            "start_time": past.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(stats_start.timestamp() * 1000),
                "end": int((stats_start + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(10),
                "min": pytest.approx(10),
                "max": pytest.approx(10),
                "last_reset": None,
            }
        ]
    }

    start_of_day = stats_top_of_hour.replace(hour=0, minute=0)
    await client.send_json(
        {
            "id": 4,
            "type": "recorder/statistics_during_period",
            "start_time": stats_top_of_hour.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "day",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "start": int(start_of_day.timestamp() * 1000),
                "end": int((start_of_day + timedelta(days=1)).timestamp() * 1000),
                "mean": pytest.approx(10),
                "min": pytest.approx(10),
                "max": pytest.approx(10),
                "last_reset": None,
            }
        ]
    }

    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {}


async def test_statistics_during_period_bad_start_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": "cats",
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_start_time"


async def test_statistics_during_period_bad_end_time(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period."""
    now = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": "dogs",
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_end_time"


async def test_statistics_during_period_no_statistic_ids(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period without passing statistic_ids."""
    now = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(seconds=1)).isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_statistics_during_period_empty_statistic_ids(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistics_during_period with passing an empty list of statistic_ids."""
    now = dt_util.utcnow()

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": [],
            "end_time": (now + timedelta(seconds=1)).isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


@pytest.mark.parametrize(
    ("units", "attributes", "display_unit", "statistics_unit", "unit_class"),
    [
        (US_CUSTOMARY_SYSTEM, DISTANCE_SENSOR_M_ATTRIBUTES, "m", "m", "distance"),
        (METRIC_SYSTEM, DISTANCE_SENSOR_M_ATTRIBUTES, "m", "m", "distance"),
        (
            US_CUSTOMARY_SYSTEM,
            DISTANCE_SENSOR_FT_ATTRIBUTES,
            "ft",
            "ft",
            "distance",
        ),
        (METRIC_SYSTEM, DISTANCE_SENSOR_FT_ATTRIBUTES, "ft", "ft", "distance"),
        (US_CUSTOMARY_SYSTEM, ENERGY_SENSOR_WH_ATTRIBUTES, "Wh", "Wh", "energy"),
        (METRIC_SYSTEM, ENERGY_SENSOR_WH_ATTRIBUTES, "Wh", "Wh", "energy"),
        (US_CUSTOMARY_SYSTEM, GAS_SENSOR_FT3_ATTRIBUTES, "ft³", "ft³", "volume"),
        (METRIC_SYSTEM, GAS_SENSOR_FT3_ATTRIBUTES, "ft³", "ft³", "volume"),
        (US_CUSTOMARY_SYSTEM, POWER_SENSOR_KW_ATTRIBUTES, "kW", "kW", "power"),
        (METRIC_SYSTEM, POWER_SENSOR_KW_ATTRIBUTES, "kW", "kW", "power"),
        (
            US_CUSTOMARY_SYSTEM,
            PRESSURE_SENSOR_HPA_ATTRIBUTES,
            "hPa",
            "hPa",
            "pressure",
        ),
        (METRIC_SYSTEM, PRESSURE_SENSOR_HPA_ATTRIBUTES, "hPa", "hPa", "pressure"),
        (US_CUSTOMARY_SYSTEM, SPEED_SENSOR_KPH_ATTRIBUTES, "km/h", "km/h", "speed"),
        (METRIC_SYSTEM, SPEED_SENSOR_KPH_ATTRIBUTES, "km/h", "km/h", "speed"),
        (
            US_CUSTOMARY_SYSTEM,
            TEMPERATURE_SENSOR_C_ATTRIBUTES,
            "°C",
            "°C",
            "temperature",
        ),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_C_ATTRIBUTES, "°C", "°C", "temperature"),
        (
            US_CUSTOMARY_SYSTEM,
            TEMPERATURE_SENSOR_F_ATTRIBUTES,
            "°F",
            "°F",
            "temperature",
        ),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_F_ATTRIBUTES, "°F", "°F", "temperature"),
        (US_CUSTOMARY_SYSTEM, VOLUME_SENSOR_FT3_ATTRIBUTES, "ft³", "ft³", "volume"),
        (METRIC_SYSTEM, VOLUME_SENSOR_FT3_ATTRIBUTES, "ft³", "ft³", "volume"),
        (
            US_CUSTOMARY_SYSTEM,
            VOLUME_SENSOR_FT3_ATTRIBUTES_TOTAL,
            "ft³",
            "ft³",
            "volume",
        ),
        (METRIC_SYSTEM, VOLUME_SENSOR_FT3_ATTRIBUTES_TOTAL, "ft³", "ft³", "volume"),
    ],
)
async def test_list_statistic_ids(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    display_unit,
    statistics_unit,
    unit_class,
) -> None:
    """Test list_statistic_ids."""
    now = dt_util.utcnow()
    has_mean = attributes["state_class"] == "measurement"
    has_sum = not has_mean

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    await client.send_json({"id": 2, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    # Remove the state, statistics will now be fetched from the database
    hass.states.async_remove("sensor.test")
    await hass.async_block_till_done()

    await client.send_json({"id": 3, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]

    await client.send_json(
        {"id": 4, "type": "recorder/list_statistic_ids", "statistic_type": "dogs"}
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json(
        {"id": 5, "type": "recorder/list_statistic_ids", "statistic_type": "mean"}
    )
    response = await client.receive_json()
    assert response["success"]
    if has_mean:
        assert response["result"] == [
            {
                "statistic_id": "sensor.test",
                "display_unit_of_measurement": display_unit,
                "has_mean": has_mean,
                "has_sum": has_sum,
                "name": None,
                "source": "recorder",
                "statistics_unit_of_measurement": statistics_unit,
                "unit_class": unit_class,
            }
        ]
    else:
        assert response["result"] == []

    await client.send_json(
        {"id": 6, "type": "recorder/list_statistic_ids", "statistic_type": "sum"}
    )
    response = await client.receive_json()
    assert response["success"]
    if has_sum:
        assert response["result"] == [
            {
                "statistic_id": "sensor.test",
                "display_unit_of_measurement": display_unit,
                "has_mean": has_mean,
                "has_sum": has_sum,
                "name": None,
                "source": "recorder",
                "statistics_unit_of_measurement": statistics_unit,
                "unit_class": unit_class,
            }
        ]
    else:
        assert response["result"] == []


@pytest.mark.parametrize(
    ("attributes", "attributes2", "display_unit", "statistics_unit", "unit_class"),
    [
        (
            DISTANCE_SENSOR_M_ATTRIBUTES,
            DISTANCE_SENSOR_FT_ATTRIBUTES,
            "ft",
            "m",
            "distance",
        ),
        (
            ENERGY_SENSOR_WH_ATTRIBUTES,
            ENERGY_SENSOR_KWH_ATTRIBUTES,
            "kWh",
            "Wh",
            "energy",
        ),
        (GAS_SENSOR_FT3_ATTRIBUTES, GAS_SENSOR_M3_ATTRIBUTES, "m³", "ft³", "volume"),
        (POWER_SENSOR_KW_ATTRIBUTES, POWER_SENSOR_W_ATTRIBUTES, "W", "kW", "power"),
        (
            PRESSURE_SENSOR_HPA_ATTRIBUTES,
            PRESSURE_SENSOR_PA_ATTRIBUTES,
            "Pa",
            "hPa",
            "pressure",
        ),
        (
            SPEED_SENSOR_KPH_ATTRIBUTES,
            SPEED_SENSOR_MPH_ATTRIBUTES,
            "mph",
            "km/h",
            "speed",
        ),
        (
            TEMPERATURE_SENSOR_C_ATTRIBUTES,
            TEMPERATURE_SENSOR_F_ATTRIBUTES,
            "°F",
            "°C",
            "temperature",
        ),
        (
            VOLUME_SENSOR_FT3_ATTRIBUTES,
            VOLUME_SENSOR_M3_ATTRIBUTES,
            "m³",
            "ft³",
            "volume",
        ),
    ],
)
async def test_list_statistic_ids_unit_change(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    attributes,
    attributes2,
    display_unit,
    statistics_unit,
    unit_class,
) -> None:
    """Test list_statistic_ids."""
    now = dt_util.utcnow()
    has_mean = attributes["state_class"] == "measurement"
    has_sum = not has_mean

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)

    await client.send_json({"id": 2, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": statistics_unit,
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]

    # Change the state unit
    hass.states.async_set("sensor.test", 10, attributes=attributes2)

    await client.send_json({"id": 3, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]


async def test_validate_statistics(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test validate_statistics can be called."""
    id = 1

    def next_id():
        nonlocal id
        id += 1
        return id

    async def assert_validation_result(client, expected_result):
        await client.send_json(
            {"id": next_id(), "type": "recorder/validate_statistics"}
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    # No statistics, no state - empty response
    client = await hass_ws_client()
    await assert_validation_result(client, {})


async def test_clear_statistics(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES
    state = 10
    value = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test1", state, attributes=attributes)
    hass.states.async_set("sensor.test2", state * 2, attributes=attributes)
    hass.states.async_set("sensor.test3", state * 3, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test1", "sensor.test2", "sensor.test3"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    expected_response = {
        "sensor.test1": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(value),
                "min": pytest.approx(value),
                "max": pytest.approx(value),
                "last_reset": None,
            }
        ],
        "sensor.test2": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(value * 2),
                "min": pytest.approx(value * 2),
                "max": pytest.approx(value * 2),
                "last_reset": None,
            }
        ],
        "sensor.test3": [
            {
                "start": int(now.timestamp() * 1000),
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "mean": pytest.approx(value * 3),
                "min": pytest.approx(value * 3),
                "max": pytest.approx(value * 3),
                "last_reset": None,
            }
        ],
    }
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 3,
            "type": "recorder/statistics_during_period",
            "statistic_ids": ["sensor.test1", "sensor.test2", "sensor.test3"],
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == expected_response

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test1", "sensor.test3"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "statistic_ids": ["sensor.test1", "sensor.test2", "sensor.test3"],
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sensor.test2": expected_response["sensor.test2"]}


@pytest.mark.parametrize(
    ("new_unit", "new_unit_class", "new_display_unit"),
    [("dogs", None, "dogs"), (None, "unitless", None), ("W", "power", "kW")],
)
async def test_update_statistics_metadata(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    new_unit,
    new_unit_class,
    new_display_unit,
) -> None:
    """Test removing statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kW",
            "unit_class": "power",
        }
    ]

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/update_statistics_metadata",
            "statistic_id": "sensor.test",
            "unit_of_measurement": new_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json({"id": 3, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": new_display_unit,
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": new_unit,
            "unit_class": new_unit_class,
        }
    ]

    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "units": {"power": "W"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "last_reset": None,
                "max": 10.0,
                "mean": 10.0,
                "min": 10.0,
                "start": int(now.timestamp() * 1000),
            }
        ],
    }


async def test_change_statistics_unit(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test change unit of recorded statistics."""
    now = dt_util.utcnow()

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kW",
            "unit_class": "power",
        }
    ]

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "last_reset": None,
                "max": 10.0,
                "mean": 10.0,
                "min": 10.0,
                "start": int(now.timestamp() * 1000),
            }
        ],
    }

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "new_unit_of_measurement": "W",
            "old_unit_of_measurement": "kW",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json({"id": 4, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "W",
            "unit_class": "power",
        }
    ]

    await client.send_json(
        {
            "id": 5,
            "type": "recorder/statistics_during_period",
            "start_time": now.isoformat(),
            "statistic_ids": ["sensor.test"],
            "period": "5minute",
            "units": {"power": "W"},
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "sensor.test": [
            {
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "last_reset": None,
                "max": 10000.0,
                "mean": 10000.0,
                "min": 10000.0,
                "start": int(now.timestamp() * 1000),
            }
        ],
    }

    # Changing to the same unit is allowed but does nothing
    await client.send_json(
        {
            "id": 6,
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "new_unit_of_measurement": "W",
            "old_unit_of_measurement": "W",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json({"id": 7, "type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "W",
            "unit_class": "power",
        }
    ]


async def test_change_statistics_unit_errors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test change unit of recorded statistics."""
    now = dt_util.utcnow()
    ws_id = 0

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    expected_statistic_ids = [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kW",
            "unit_class": "power",
        }
    ]

    expected_statistics = {
        "sensor.test": [
            {
                "end": int((now + timedelta(minutes=5)).timestamp() * 1000),
                "last_reset": None,
                "max": 10.0,
                "mean": 10.0,
                "min": 10.0,
                "start": int(now.timestamp() * 1000),
            }
        ],
    }

    async def assert_statistic_ids(expected):
        nonlocal ws_id
        ws_id += 1
        await client.send_json({"id": ws_id, "type": "recorder/list_statistic_ids"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected

    async def assert_statistics(expected):
        nonlocal ws_id
        ws_id += 1
        await client.send_json(
            {
                "id": ws_id,
                "type": "recorder/statistics_during_period",
                "start_time": now.isoformat(),
                "statistic_ids": ["sensor.test"],
                "period": "5minute",
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set("sensor.test", state, attributes=attributes)
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await assert_statistic_ids(expected_statistic_ids)
    await assert_statistics(expected_statistics)

    # Try changing to an invalid unit
    ws_id += 1
    await client.send_json(
        {
            "id": ws_id,
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "old_unit_of_measurement": "kW",
            "new_unit_of_measurement": "dogs",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["message"] == "Can't convert kW to dogs"

    await async_recorder_block_till_done(hass)

    await assert_statistic_ids(expected_statistic_ids)
    await assert_statistics(expected_statistics)

    # Try changing from the wrong unit
    ws_id += 1
    await client.send_json(
        {
            "id": ws_id,
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "old_unit_of_measurement": "W",
            "new_unit_of_measurement": "kW",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_recorder_block_till_done(hass)

    assert "Could not change statistics unit for sensor.test" in caplog.text
    await assert_statistic_ids(expected_statistic_ids)
    await assert_statistics(expected_statistics)


async def test_recorder_info(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting recorder status."""
    client = await hass_ws_client()

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "backlog": 0,
        "max_backlog": 65000,
        "migration_in_progress": False,
        "migration_is_live": False,
        "recording": True,
        "thread_running": True,
    }


async def test_recorder_info_no_recorder(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting recorder status when recorder is not present."""
    client = await hass_ws_client()

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_recorder_info_bad_recorder_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting recorder status when recorder is not started."""
    config = {recorder.CONF_DB_URL: "sqlite://no_file", recorder.CONF_DB_RETRY_WAIT: 0}

    client = await hass_ws_client()

    with patch("homeassistant.components.recorder.migration.migrate_schema"):
        recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN not in hass.config.components
    await hass.async_block_till_done()

    # Wait for recorder to shut down
    await hass.async_add_executor_job(recorder.get_instance(hass).join)

    await client.send_json({"id": 1, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["recording"] is False
    assert response["result"]["thread_running"] is False


async def test_recorder_info_migration_queue_exhausted(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting recorder status when recorder queue is exhausted."""
    assert recorder.util.async_migration_in_progress(hass) is False

    migration_done = threading.Event()

    real_migration = recorder.migration._apply_update

    def stalled_migration(*args):
        """Make migration stall."""
        nonlocal migration_done
        migration_done.wait()
        return real_migration(*args)

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics"
    ), patch(
        "homeassistant.components.recorder.core.create_engine",
        new=create_engine_test,
    ), patch.object(
        recorder.core, "MAX_QUEUE_BACKLOG_MIN_VALUE", 1
    ), patch.object(
        recorder.core, "QUEUE_PERCENTAGE_ALLOWED_AVAILABLE_MEMORY", 0
    ), patch(
        "homeassistant.components.recorder.migration._apply_update",
        wraps=stalled_migration,
    ):
        recorder_helper.async_initialize_recorder(hass)
        hass.create_task(
            async_setup_component(
                hass, "recorder", {"recorder": {"db_url": "sqlite://"}}
            )
        )
        await recorder_helper.async_wait_recorder(hass)
        hass.states.async_set("my.entity", "on", {})
        await hass.async_block_till_done()

        # Detect queue full
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
        await hass.async_block_till_done()

        client = await hass_ws_client()

        # Check the status
        await client.send_json({"id": 1, "type": "recorder/info"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"]["migration_in_progress"] is True
        assert response["result"]["recording"] is False
        assert response["result"]["thread_running"] is True

    # Let migration finish
    migration_done.set()
    await async_wait_recording_done(hass)

    # Check the status after migration finished
    await client.send_json({"id": 2, "type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["migration_in_progress"] is False
    assert response["result"]["recording"] is True
    assert response["result"]["thread_running"] is True


async def test_backup_start_no_recorder(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_supervisor_access_token: str,
) -> None:
    """Test getting backup start when recorder is not present."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    await client.send_json({"id": 1, "type": "backup/start"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_backup_start_timeout(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_supervisor_access_token: str,
    recorder_db_url: str,
) -> None:
    """Test getting backup start when recorder is not present."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite: Locking is not implemented for other engines
        return

    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    with patch.object(recorder.core, "DB_LOCK_TIMEOUT", 0):
        try:
            await client.send_json({"id": 1, "type": "backup/start"})
            response = await client.receive_json()
            assert not response["success"]
            assert response["error"]["code"] == "timeout_error"
        finally:
            await client.send_json({"id": 2, "type": "backup/end"})


async def test_backup_end(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_supervisor_access_token: str,
) -> None:
    """Test backup start."""
    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "backup/start"})
    response = await client.receive_json()
    assert response["success"]

    await client.send_json({"id": 2, "type": "backup/end"})
    response = await client.receive_json()
    assert response["success"]


async def test_backup_end_without_start(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_supervisor_access_token: str,
    recorder_db_url: str,
) -> None:
    """Test backup start."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite: Locking is not implemented for other engines
        return

    client = await hass_ws_client(hass, hass_supervisor_access_token)

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    await client.send_json({"id": 1, "type": "backup/end"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "database_unlock_failed"


@pytest.mark.parametrize(
    ("units", "attributes", "unit", "unit_class"),
    [
        (METRIC_SYSTEM, ENERGY_SENSOR_KWH_ATTRIBUTES, "kWh", "energy"),
        (METRIC_SYSTEM, ENERGY_SENSOR_WH_ATTRIBUTES, "kWh", "energy"),
        (METRIC_SYSTEM, GAS_SENSOR_FT3_ATTRIBUTES, "m³", "volume"),
        (METRIC_SYSTEM, GAS_SENSOR_M3_ATTRIBUTES, "m³", "volume"),
        (METRIC_SYSTEM, POWER_SENSOR_W_ATTRIBUTES, "W", "power"),
        (METRIC_SYSTEM, POWER_SENSOR_KW_ATTRIBUTES, "W", "power"),
        (METRIC_SYSTEM, PRESSURE_SENSOR_PA_ATTRIBUTES, "Pa", "pressure"),
        (METRIC_SYSTEM, PRESSURE_SENSOR_HPA_ATTRIBUTES, "Pa", "pressure"),
        (METRIC_SYSTEM, SPEED_SENSOR_KPH_ATTRIBUTES, "m/s", "speed"),
        (METRIC_SYSTEM, SPEED_SENSOR_MPH_ATTRIBUTES, "m/s", "speed"),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_C_ATTRIBUTES, "°C", "temperature"),
        (METRIC_SYSTEM, TEMPERATURE_SENSOR_F_ATTRIBUTES, "°C", "temperature"),
        (METRIC_SYSTEM, VOLUME_SENSOR_FT3_ATTRIBUTES, "m³", "volume"),
        (METRIC_SYSTEM, VOLUME_SENSOR_M3_ATTRIBUTES, "m³", "volume"),
    ],
)
async def test_get_statistics_metadata(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    units,
    attributes,
    unit,
    unit_class,
) -> None:
    """Test get_statistics_metadata."""
    now = dt_util.utcnow()
    has_mean = attributes["state_class"] == "measurement"
    has_sum = not has_mean

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "recorder/get_statistics_metadata"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))
    external_energy_statistics_1 = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 5,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 8,
        },
    )
    external_energy_metadata_1 = {
        "has_mean": has_mean,
        "has_sum": has_sum,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_gas",
        "unit_of_measurement": unit,
    }

    async_add_external_statistics(
        hass, external_energy_metadata_1, external_energy_statistics_1
    )
    await async_wait_recording_done(hass)

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/get_statistics_metadata",
            "statistic_ids": ["test:total_gas"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "test:total_gas",
            "display_unit_of_measurement": unit,
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": "Total imported energy",
            "source": "test",
            "statistics_unit_of_measurement": unit,
            "unit_class": unit_class,
        }
    ]

    hass.states.async_set("sensor.test", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    hass.states.async_set("sensor.test2", 10, attributes=attributes)
    await async_wait_recording_done(hass)

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/get_statistics_metadata",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": attributes["unit_of_measurement"],
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": attributes["unit_of_measurement"],
            "unit_class": unit_class,
        }
    ]

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)
    # Remove the state, statistics will now be fetched from the database
    hass.states.async_remove("sensor.test")
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 4,
            "type": "recorder/get_statistics_metadata",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": attributes["unit_of_measurement"],
            "has_mean": has_mean,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": attributes["unit_of_measurement"],
            "unit_class": unit_class,
        }
    ]


@pytest.mark.parametrize(
    ("source", "statistic_id"),
    (
        ("test", "test:total_energy_import"),
        ("recorder", "sensor.total_energy_import"),
    ),
)
async def test_import_statistics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    source,
    statistic_id,
) -> None:
    """Test importing statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    imported_statistics1 = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    imported_statistics2 = {
        "start": period2.isoformat(),
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
    }

    await client.send_json(
        {
            "id": 1,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [imported_statistics1, imported_statistics2],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)  # TODO
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    last_stats = get_last_statistics(
        hass,
        1,
        statistic_id,
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert last_stats == {
        statistic_id: [
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 5,
        "sum": 6,
    }

    await client.send_json(
        {
            "id": 2,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [external_statistics],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(5.0),
                "sum": pytest.approx(6.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1.isoformat(),
        "max": 1,
        "mean": 2,
        "min": 3,
        "last_reset": None,
        "state": 4,
        "sum": 5,
    }

    await client.send_json(
        {
            "id": 3,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [external_statistics],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(
        hass, zero, period="hour", statistic_ids={statistic_id}
    )
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(4.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }


@pytest.mark.parametrize(
    ("source", "statistic_id"),
    (
        ("test", "test:total_energy_import"),
        ("recorder", "sensor.total_energy_import"),
    ),
)
async def test_adjust_sum_statistics_energy(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    source,
    statistic_id,
) -> None:
    """Test adjusting statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    imported_statistics1 = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    imported_statistics2 = {
        "start": period2.isoformat(),
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
    }

    await client.send_json(
        {
            "id": 1,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [imported_statistics1, imported_statistics2],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)  # TODO
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }

    # Adjust previously inserted statistics in kWh
    await client.send_json(
        {
            "id": 4,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
            "adjustment_unit_of_measurement": "kWh",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": pytest.approx(None),
                "mean": pytest.approx(None),
                "min": pytest.approx(None),
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(1003.0),
            },
        ]
    }

    # Adjust previously inserted statistics in MWh
    await client.send_json(
        {
            "id": 5,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 2.0,
            "adjustment_unit_of_measurement": "MWh",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": pytest.approx(None),
                "mean": pytest.approx(None),
                "min": pytest.approx(None),
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3003.0),
            },
        ]
    }


@pytest.mark.parametrize(
    ("source", "statistic_id"),
    (
        ("test", "test:total_gas"),
        ("recorder", "sensor.total_gas"),
    ),
)
async def test_adjust_sum_statistics_gas(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    source,
    statistic_id,
) -> None:
    """Test adjusting statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    imported_statistics1 = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    imported_statistics2 = {
        "start": period2.isoformat(),
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "m³",
    }

    await client.send_json(
        {
            "id": 1,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [imported_statistics1, imported_statistics2],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)  # TODO
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "m³",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "m³",
            "unit_class": "volume",
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "m³",
            },
        )
    }

    # Adjust previously inserted statistics in m³
    await client.send_json(
        {
            "id": 4,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
            "adjustment_unit_of_measurement": "m³",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": pytest.approx(None),
                "mean": pytest.approx(None),
                "min": pytest.approx(None),
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(1003.0),
            },
        ]
    }

    # Adjust previously inserted statistics in ft³
    await client.send_json(
        {
            "id": 5,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 35.3147,  # ~1 m³
            "adjustment_unit_of_measurement": "ft³",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": pytest.approx(None),
                "mean": pytest.approx(None),
                "min": pytest.approx(None),
                "last_reset": None,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(1004),
            },
        ]
    }


@pytest.mark.parametrize(
    (
        "state_unit",
        "statistic_unit",
        "unit_class",
        "factor",
        "valid_units",
        "invalid_units",
    ),
    (
        ("kWh", "kWh", "energy", 1, ("Wh", "kWh", "MWh"), ("ft³", "m³", "cats", None)),
        ("MWh", "MWh", "energy", 1, ("Wh", "kWh", "MWh"), ("ft³", "m³", "cats", None)),
        ("m³", "m³", "volume", 1, ("ft³", "m³"), ("Wh", "kWh", "MWh", "cats", None)),
        ("ft³", "ft³", "volume", 1, ("ft³", "m³"), ("Wh", "kWh", "MWh", "cats", None)),
        ("dogs", "dogs", None, 1, ("dogs",), ("cats", None)),
        (None, None, "unitless", 1, (None,), ("cats",)),
    ),
)
async def test_adjust_sum_statistics_errors(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    state_unit,
    statistic_unit,
    unit_class,
    factor,
    valid_units,
    invalid_units,
) -> None:
    """Test incorrectly adjusting statistics."""
    statistic_id = "sensor.total_energy_import"
    source = "recorder"
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    imported_statistics1 = {
        "start": period1.isoformat(),
        "last_reset": None,
        "state": 0,
        "sum": 2,
    }
    imported_statistics2 = {
        "start": period2.isoformat(),
        "last_reset": None,
        "state": 1,
        "sum": 3,
    }

    imported_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": statistic_unit,
    }

    await client.send_json(
        {
            "id": 1,
            "type": "recorder/import_statistics",
            "metadata": imported_metadata,
            "stats": [imported_statistics1, imported_statistics2],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": period1.timestamp(),
                "end": (period1 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(0.0 * factor),
                "sum": pytest.approx(2.0 * factor),
            },
            {
                "start": period2.timestamp(),
                "end": (period2 + timedelta(hours=1)).timestamp(),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0 * factor),
                "sum": pytest.approx(3.0 * factor),
            },
        ]
    }
    previous_stats = stats
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": state_unit,
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": state_unit,
            "unit_class": unit_class,
        }
    ]
    metadata = get_metadata(hass, statistic_ids={statistic_id})
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": state_unit,
            },
        )
    }

    # Try to adjust statistics
    msg_id = 2
    await client.send_json(
        {
            "id": msg_id,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": "sensor.does_not_exist",
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
            "adjustment_unit_of_measurement": statistic_unit,
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_statistic_id"

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == previous_stats

    for unit in invalid_units:
        msg_id += 1
        await client.send_json(
            {
                "id": msg_id,
                "type": "recorder/adjust_sum_statistics",
                "statistic_id": statistic_id,
                "start_time": period2.isoformat(),
                "adjustment": 1000.0,
                "adjustment_unit_of_measurement": unit,
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert response["error"]["code"] == "invalid_units"

        await async_wait_recording_done(hass)
        stats = statistics_during_period(hass, zero, period="hour")
        assert stats == previous_stats

    for unit in valid_units:
        msg_id += 1
        await client.send_json(
            {
                "id": msg_id,
                "type": "recorder/adjust_sum_statistics",
                "statistic_id": statistic_id,
                "start_time": period2.isoformat(),
                "adjustment": 1000.0,
                "adjustment_unit_of_measurement": unit,
            }
        )
        response = await client.receive_json()
        assert response["success"]

        await async_wait_recording_done(hass)
        stats = statistics_during_period(hass, zero, period="hour")
        assert stats != previous_stats
        previous_stats = stats
