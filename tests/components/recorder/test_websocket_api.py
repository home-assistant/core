"""The tests for sensor recorder platform."""

from collections.abc import Iterable
import datetime
from datetime import timedelta
import math
from statistics import fmean
import sys
from unittest.mock import ANY, patch

from _pytest.python_api import ApproxBase
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import recorder
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.db_schema import Statistics, StatisticsShortTerm
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    DEG_TO_RAD,
    RAD_TO_DEG,
    async_add_external_statistics,
    get_last_statistics,
    get_latest_short_term_statistics_with_session,
    get_metadata,
    get_short_term_statistics_run_cache,
    list_statistic_ids,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.recorder.websocket_api import UNIT_SCHEMA
from homeassistant.components.sensor import UNIT_CONVERTERS
from homeassistant.const import DEGREE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .common import (
    async_recorder_block_till_done,
    async_wait_recorder,
    async_wait_recording_done,
    create_engine_test,
    do_adhoc_statistics,
    get_start_time,
    statistics_during_period,
)
from .conftest import InstrumentedMigration

from tests.common import async_fire_time_changed
from tests.typing import (
    RecorderInstanceContextManager,
    RecorderInstanceGenerator,
    WebSocketGenerator,
)


@pytest.fixture
async def mock_recorder_before_hass(
    async_setup_recorder_instance: RecorderInstanceGenerator,
) -> None:
    """Set up recorder."""


AREA_SENSOR_FT_ATTRIBUTES = {
    "device_class": "area",
    "state_class": "measurement",
    "unit_of_measurement": "ft²",
}
AREA_SENSOR_M_ATTRIBUTES = {
    "device_class": "area",
    "state_class": "measurement",
    "unit_of_measurement": "m²",
}
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
    now = get_start_time(dt_util.utcnow())

    hass.config.units = US_CUSTOMARY_SYSTEM
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test",
        10,
        attributes=POWER_SENSOR_KW_ATTRIBUTES,
        timestamp=now.timestamp(),
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
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
@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("offset", [0, 1, 2])
async def test_statistic_during_period(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    offset: int,
) -> None:
    """Test statistic_during_period."""
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
        for i in range(39)
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
    for i in range(2):
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
        "has_mean": True,
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

    metadata = get_metadata(hass, statistic_ids={"sensor.test"})
    metadata_id = metadata["sensor.test"][0]
    run_cache = get_short_term_statistics_run_cache(hass)
    # Verify the import of the short term statistics
    # also updates the run cache
    assert run_cache.get_latest_ids({metadata_id}) is not None

    # No data for this period yet
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    hass.states.async_set(
        "sensor.test",
        None,
        attributes=ENERGY_SENSOR_WH_ATTRIBUTES,
        timestamp=now.timestamp(),
    )
    await client.send_json_auto_id(
        {
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
    with session_scope(hass=hass, read_only=True) as session:
        stats = get_latest_short_term_statistics_with_session(
            hass,
            session,
            {"sensor.test"},
            {"last_reset", "state", "sum"},
        )
    start = imported_stats_5min[-1]["start"].timestamp()
    end = start + (5 * 60)
    assert stats == {
        "sensor.test": [
            {
                "end": end,
                "last_reset": None,
                "start": start,
                "state": None,
                "sum": 38.0,
            }
        ]
    }


def _circular_mean(values: Iterable[StatisticData]) -> dict[str, float]:
    sin_sum = 0
    cos_sum = 0
    for x in values:
        mean = x.get("mean")
        assert mean is not None
        sin_sum += math.sin(mean * DEG_TO_RAD)
        cos_sum += math.cos(mean * DEG_TO_RAD)

    return {
        "mean": (RAD_TO_DEG * math.atan2(sin_sum, cos_sum)) % 360,
        "mean_weight": math.sqrt(sin_sum**2 + cos_sum**2),
    }


def _circular_mean_approx(
    values: Iterable[StatisticData], tolerance: float | None = None
) -> ApproxBase:
    return pytest.approx(_circular_mean(values)["mean"], abs=tolerance)


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
@pytest.mark.usefixtures("recorder_mock")
@pytest.mark.parametrize("offset", [0, 1, 2])
@pytest.mark.parametrize(
    ("step_size", "tolerance"),
    [
        (123.456, 1e-4),
        # In this case the angles are uniformly distributed and the mean is undefined.
        # This edge case is not handled by the current implementation, but the test
        # checks the behavior is consistent.
        # We could consider returning None in this case, or returning also an estimate
        # of the variance.
        (120, 10),
    ],
)
async def test_statistic_during_period_circular_mean(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    offset: int,
    step_size: float,
    tolerance: float,
) -> None:
    """Test statistic_during_period."""
    now = dt_util.utcnow()

    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    zero = now
    start = zero.replace(minute=offset * 5, second=0, microsecond=0) + timedelta(
        hours=-3
    )

    imported_stats_5min: list[StatisticData] = [
        {
            "start": (start + timedelta(minutes=5 * i)),
            "mean": (step_size * i) % 360,
            "mean_weight": 1,
        }
        for i in range(39)
    ]

    imported_stats = []
    slice_end = 12 - offset
    imported_stats.append(
        {
            "start": imported_stats_5min[0]["start"].replace(minute=0),
            **_circular_mean(imported_stats_5min[0:slice_end]),
        }
    )
    for i in range(2):
        slice_start = i * 12 + (12 - offset)
        slice_end = (i + 1) * 12 + (12 - offset)
        assert imported_stats_5min[slice_start]["start"].minute == 0
        imported_stats.append(
            {
                "start": imported_stats_5min[slice_start]["start"],
                **_circular_mean(imported_stats_5min[slice_start:slice_end]),
            }
        )

    imported_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.CIRCULAR,
        "has_sum": False,
        "name": "Wind direction",
        "source": "recorder",
        "statistic_id": "sensor.test",
        "unit_of_measurement": DEGREE,
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

    metadata = get_metadata(hass, statistic_ids={"sensor.test"})
    metadata_id = metadata["sensor.test"][0]
    run_cache = get_short_term_statistics_run_cache(hass)
    # Verify the import of the short term statistics
    # also updates the run cache
    assert run_cache.get_latest_ids({metadata_id}) is not None

    # No data for this period yet
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "mean": _circular_mean_approx(imported_stats_5min, tolerance),
        "max": None,
        "min": None,
        "change": None,
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
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min, tolerance),
        "max": None,
        "min": None,
        "change": None,
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
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min, tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should include imported_statistics_5min[26:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T06:10:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[26]["start"].isoformat() == start_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[26:], tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should also include imported_statistics_5min[26:]
    start_time = (
        dt_util.parse_datetime("2022-10-21T06:09:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[26:], tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should include imported_statistics_5min[:26]
    end_time = (
        dt_util.parse_datetime("2022-10-21T06:10:00+00:00")
        + timedelta(minutes=5 * offset)
    ).isoformat()
    assert imported_stats_5min[26]["start"].isoformat() == end_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[:26], tolerance),
        "max": None,
        "min": None,
        "change": None,
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
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[26:32], tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should include imported_statistics[2:] + imported_statistics_5min[36:]
    start_time = "2022-10-21T06:00:00+00:00"
    assert imported_stats_5min[24 - offset]["start"].isoformat() == start_time
    assert imported_stats[2]["start"].isoformat() == start_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[24 - offset :], tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should also include imported_statistics[2:] + imported_statistics_5min[36:]
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats_5min[24 - offset :], tolerance),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should include imported_statistics[2:3]
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(
            imported_stats_5min[slice_start:slice_end], tolerance
        ),
        "max": None,
        "min": None,
        "change": None,
    }

    # Test we can get only selected types
    await client.send_json_auto_id(
        {
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
            "types": ["mean"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "mean": _circular_mean_approx(imported_stats_5min, tolerance),
    }


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
async def test_statistic_during_period_hole(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistic_during_period when there are holes in the data."""
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
        for i in range(6)
    ]

    imported_metadata = {
        "has_mean": True,
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
@pytest.mark.usefixtures("recorder_mock")
async def test_statistic_during_period_hole_circular_mean(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test statistic_during_period when there are holes in the data."""
    now = dt_util.utcnow()

    await async_recorder_block_till_done(hass)
    client = await hass_ws_client()

    zero = now
    start = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=-18)

    imported_stats: list[StatisticData] = [
        {
            "start": (start + timedelta(hours=3 * i)),
            "mean": (123.456 * i) % 360,
            "mean_weight": 1,
        }
        for i in range(6)
    ]

    imported_metadata: StatisticMetaData = {
        "mean_type": StatisticMeanType.CIRCULAR,
        "has_sum": False,
        "name": "Wind direction",
        "source": "recorder",
        "statistic_id": "sensor.test",
        "unit_of_measurement": DEGREE,
    }

    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats,
        Statistics,
    )
    await async_wait_recording_done(hass)

    # This should include imported_stats[:]
    await client.send_json_auto_id(
        {
            "type": "recorder/statistic_during_period",
            "statistic_id": "sensor.test",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "mean": _circular_mean_approx(imported_stats[:]),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should also include imported_stats[:]
    start_time = "2022-10-20T13:00:00+00:00"
    end_time = "2022-10-21T05:00:00+00:00"
    assert imported_stats[0]["start"].isoformat() == start_time
    assert imported_stats[-1]["start"].isoformat() < end_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats[:]),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should also include imported_stats[:]
    start_time = "2022-10-20T13:00:00+00:00"
    end_time = "2022-10-21T08:20:00+00:00"
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats[:]),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should include imported_stats[1:4]
    start_time = "2022-10-20T16:00:00+00:00"
    end_time = "2022-10-20T23:00:00+00:00"
    assert imported_stats[1]["start"].isoformat() == start_time
    assert imported_stats[3]["start"].isoformat() < end_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats[1:4]),
        "max": None,
        "min": None,
        "change": None,
    }

    # This should also include imported_stats[1:4]
    start_time = "2022-10-20T15:00:00+00:00"
    end_time = "2022-10-21T00:00:00+00:00"
    assert imported_stats[1]["start"].isoformat() > start_time
    assert imported_stats[3]["start"].isoformat() < end_time
    await client.send_json_auto_id(
        {
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
        "mean": _circular_mean_approx(imported_stats[1:4]),
        "max": None,
        "min": None,
        "change": None,
    }


@pytest.mark.parametrize(
    "frozen_time",
    [
        # This is the normal case, all statistics runs are available
        datetime.datetime(2022, 10, 21, 6, 31, tzinfo=datetime.UTC),
        # Statistic only available up until 6:25, this can happen if
        # core has been shut down for an hour
        datetime.datetime(2022, 10, 21, 7, 31, tzinfo=datetime.UTC),
    ],
)
async def test_statistic_during_period_partial_overlap(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    frozen_time: datetime.datetime,
) -> None:
    """Test statistic_during_period."""
    client = await hass_ws_client()

    freezer.move_to(frozen_time)
    now = dt_util.utcnow()

    await async_recorder_block_till_done(hass)

    zero = now
    start = zero.replace(hour=0, minute=0, second=0, microsecond=0)

    # Sum shall be tracking a hypothetical sensor that is 0 at midnight, and grows by 1 per minute.
    # The test will have 4 hours of LTS-only data (0:00-3:59:59), followed by 2 hours of overlapping STS/LTS (4:00-5:59:59), followed by 30 minutes of STS only (6:00-6:29:59)
    # similar to how a real recorder might look after purging STS.

    # The datapoint at i=0 (start = 0:00) will be 60 as that is the growth during the hour starting at the start period
    imported_stats_hours = [
        {
            "start": (start + timedelta(hours=i)),
            "min": i * 60,
            "max": i * 60 + 60,
            "mean": i * 60 + 30,
            "sum": (i + 1) * 60,
        }
        for i in range(6)
    ]

    # The datapoint at i=0 (start = 4:00) would be the sensor's value at t=4:05, or 245
    imported_stats_5min = [
        {
            "start": (start + timedelta(hours=4, minutes=5 * i)),
            "min": 4 * 60 + i * 5,
            "max": 4 * 60 + i * 5 + 5,
            "mean": 4 * 60 + i * 5 + 2.5,
            "sum": 4 * 60 + (i + 1) * 5,
        }
        for i in range(30)
    ]

    assert imported_stats_hours[-1]["sum"] == 360
    assert imported_stats_hours[-1]["start"] == start.replace(
        hour=5, minute=0, second=0, microsecond=0
    )
    assert imported_stats_5min[-1]["sum"] == 390
    assert imported_stats_5min[-1]["start"] == start.replace(
        hour=6, minute=25, second=0, microsecond=0
    )

    statId = "sensor.test_overlapping"
    imported_metadata = {
        "has_mean": True,
        "has_sum": True,
        "name": "Total imported energy overlapping",
        "source": "recorder",
        "statistic_id": statId,
        "unit_of_measurement": "kWh",
    }

    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats_hours,
        Statistics,
    )
    recorder.get_instance(hass).async_import_statistics(
        imported_metadata,
        imported_stats_5min,
        StatisticsShortTerm,
    )
    await async_wait_recording_done(hass)

    metadata = get_metadata(hass, statistic_ids={statId})
    metadata_id = metadata[statId][0]
    run_cache = get_short_term_statistics_run_cache(hass)
    # Verify the import of the short term statistics
    # also updates the run cache
    assert run_cache.get_latest_ids({metadata_id}) is not None

    # Get all the stats, should consider all hours and 5mins
    await client.send_json_auto_id(
        {
            "type": "recorder/statistic_during_period",
            "statistic_id": statId,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "change": 390,
        "max": 390,
        "min": 0,
        "mean": 195,
    }

    async def assert_stat_during_fixed(client, start_time, end_time, expect):
        json = {
            "type": "recorder/statistic_during_period",
            "types": list(expect.keys()),
            "statistic_id": statId,
            "fixed_period": {},
        }
        if start_time:
            json["fixed_period"]["start_time"] = start_time.isoformat()
        if end_time:
            json["fixed_period"]["end_time"] = end_time.isoformat()

        await client.send_json_auto_id(json)
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expect

    # One hours worth of growth in LTS-only
    start_time = start.replace(hour=1)
    end_time = start.replace(hour=2)
    await assert_stat_during_fixed(
        client, start_time, end_time, {"change": 60, "min": 60, "max": 120, "mean": 90}
    )

    # Five minutes of growth in STS-only
    start_time = start.replace(hour=6, minute=15)
    end_time = start.replace(hour=6, minute=20)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 5,
            "min": 6 * 60 + 15,
            "max": 6 * 60 + 20,
            "mean": 6 * 60 + (15 + 20) / 2,
        },
    )

    # Six minutes of growth in STS-only
    start_time = start.replace(hour=6, minute=14)
    end_time = start.replace(hour=6, minute=20)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 5,
            "min": 6 * 60 + 15,
            "max": 6 * 60 + 20,
            "mean": 6 * 60 + (15 + 20) / 2,
        },
    )

    # Six minutes of growth in STS-only
    # 5-minute Change includes start times exactly on or before a statistics start, but end times are not counted unless they are greater than start.
    start_time = start.replace(hour=6, minute=15)
    end_time = start.replace(hour=6, minute=21)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 10,
            "min": 6 * 60 + 15,
            "max": 6 * 60 + 25,
            "mean": 6 * 60 + (15 + 25) / 2,
        },
    )

    # Five minutes of growth in overlapping LTS+STS
    start_time = start.replace(hour=5, minute=15)
    end_time = start.replace(hour=5, minute=20)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 5,
            "min": 5 * 60 + 15,
            "max": 5 * 60 + 20,
            "mean": 5 * 60 + (15 + 20) / 2,
        },
    )

    # Five minutes of growth in overlapping LTS+STS (start of hour)
    start_time = start.replace(hour=5, minute=0)
    end_time = start.replace(hour=5, minute=5)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 5, "min": 5 * 60, "max": 5 * 60 + 5, "mean": 5 * 60 + (5) / 2},
    )

    # Five minutes of growth in overlapping LTS+STS (end of hour)
    start_time = start.replace(hour=4, minute=55)
    end_time = start.replace(hour=5, minute=0)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 5,
            "min": 4 * 60 + 55,
            "max": 5 * 60,
            "mean": 4 * 60 + (55 + 60) / 2,
        },
    )

    # Five minutes of growth in STS-only, with a minute offset. Despite that this does not cover the full period, result is still 5
    start_time = start.replace(hour=6, minute=16)
    end_time = start.replace(hour=6, minute=21)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 5,
            "min": 6 * 60 + 20,
            "max": 6 * 60 + 25,
            "mean": 6 * 60 + (20 + 25) / 2,
        },
    )

    # 7 minutes of growth in STS-only, spanning two intervals
    start_time = start.replace(hour=6, minute=14)
    end_time = start.replace(hour=6, minute=21)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 10,
            "min": 6 * 60 + 15,
            "max": 6 * 60 + 25,
            "mean": 6 * 60 + (15 + 25) / 2,
        },
    )

    # One hours worth of growth in LTS-only, with arbitrary minute offsets
    # Since this does not fully cover the hour, result is None?
    start_time = start.replace(hour=1, minute=40)
    end_time = start.replace(hour=2, minute=12)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": None, "min": None, "max": None, "mean": None},
    )

    # One hours worth of growth in LTS-only, with arbitrary minute offsets, covering a whole 1-hour period
    start_time = start.replace(hour=1, minute=40)
    end_time = start.replace(hour=3, minute=12)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 60, "min": 120, "max": 180, "mean": 150},
    )

    # 90 minutes of growth in window overlapping LTS+STS/STS-only (4:41 - 6:11)
    start_time = start.replace(hour=4, minute=41)
    end_time = start_time + timedelta(minutes=90)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {
            "change": 90,
            "min": 4 * 60 + 45,
            "max": 4 * 60 + 45 + 90,
            "mean": 4 * 60 + 45 + 45,
        },
    )

    # 4 hours of growth in overlapping LTS-only/LTS+STS (2:01-6:01)
    start_time = start.replace(hour=2, minute=1)
    end_time = start_time + timedelta(minutes=240)
    # 60 from LTS (3:00-3:59), 125 from STS (25 intervals) (4:00-6:01)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 185, "min": 3 * 60, "max": 3 * 60 + 185, "mean": 3 * 60 + 185 / 2},
    )

    # 4 hours of growth in overlapping LTS-only/LTS+STS (1:31-5:31)
    start_time = start.replace(hour=1, minute=31)
    end_time = start_time + timedelta(minutes=240)
    # 120 from LTS (2:00-3:59), 95 from STS (19 intervals) 4:00-5:31
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 215, "min": 2 * 60, "max": 2 * 60 + 215, "mean": 2 * 60 + 215 / 2},
    )

    # 5 hours of growth, start time only (1:31-end)
    start_time = start.replace(hour=1, minute=31)
    end_time = None
    # will be actually 2:00 - end
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 4 * 60 + 30, "min": 120, "max": 390, "mean": (390 + 120) / 2},
    )

    # 5 hours of growth, end_time_only (0:00-5:00)
    start_time = None
    end_time = start.replace(hour=5)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 5 * 60, "min": 0, "max": 5 * 60, "mean": (5 * 60) / 2},
    )

    # 5 hours 1 minute of growth, end_time_only (0:00-5:01)
    start_time = None
    end_time = start.replace(hour=5, minute=1)
    # 4 hours LTS, 1 hour and 5 minutes STS (4:00-5:01)
    await assert_stat_during_fixed(
        client,
        start_time,
        end_time,
        {"change": 5 * 60 + 5, "min": 0, "max": 5 * 60 + 5, "mean": (5 * 60 + 5) / 2},
    )


@pytest.mark.freeze_time(datetime.datetime(2022, 10, 21, 7, 25, tzinfo=datetime.UTC))
@pytest.mark.parametrize(
    ("calendar_period", "start_time", "end_time"),
    [
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
    ],
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
        await client.send_json_auto_id(
            {
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
        (AREA_SENSOR_M_ATTRIBUTES, 10, 10, {"area": "cm²"}, 100000),
        (AREA_SENSOR_M_ATTRIBUTES, 10, 10, {"area": "m²"}, 10),
        (AREA_SENSOR_M_ATTRIBUTES, 10, 10, {"area": "ft²"}, 107.639),
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
    now = get_start_time(dt_util.utcnow())

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test", state, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    # Query in state unit
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    now = get_start_time(dt_util.utcnow())

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test", 0, attributes=attributes, timestamp=now.timestamp()
    )
    hass.states.async_set(
        "sensor.test", state, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_wait_recording_done(hass)

    client = await hass_ws_client()

    # Query in state unit
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
        {"area": "L"},
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await hass.config.async_set_time_zone("UTC")
    now = get_start_time(dt_util.utcnow())

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
    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
        (US_CUSTOMARY_SYSTEM, AREA_SENSOR_M_ATTRIBUTES, "m²", "m²", "area"),
        (METRIC_SYSTEM, AREA_SENSOR_M_ATTRIBUTES, "m²", "m²", "area"),
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
    now = get_start_time(dt_util.utcnow())
    has_mean = attributes["state_class"] == "measurement"
    mean_type = StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE
    has_sum = not has_mean

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    hass.states.async_set(
        "sensor.test", 10, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "mean_type": mean_type,
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

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "mean_type": mean_type,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]

    await client.send_json_auto_id(
        {"type": "recorder/list_statistic_ids", "statistic_type": "dogs"}
    )
    response = await client.receive_json()
    assert not response["success"]

    await client.send_json_auto_id(
        {"type": "recorder/list_statistic_ids", "statistic_type": "mean"}
    )
    response = await client.receive_json()
    assert response["success"]
    if has_mean:
        assert response["result"] == [
            {
                "statistic_id": "sensor.test",
                "display_unit_of_measurement": display_unit,
                "has_mean": has_mean,
                "mean_type": mean_type,
                "has_sum": has_sum,
                "name": None,
                "source": "recorder",
                "statistics_unit_of_measurement": statistics_unit,
                "unit_class": unit_class,
            }
        ]
    else:
        assert response["result"] == []

    await client.send_json_auto_id(
        {"type": "recorder/list_statistic_ids", "statistic_type": "sum"}
    )
    response = await client.receive_json()
    assert response["success"]
    if has_sum:
        assert response["result"] == [
            {
                "statistic_id": "sensor.test",
                "display_unit_of_measurement": display_unit,
                "has_mean": has_mean,
                "mean_type": mean_type,
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
            AREA_SENSOR_M_ATTRIBUTES,
            AREA_SENSOR_FT_ATTRIBUTES,
            "ft²",
            "m²",
            "area",
        ),
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
    now = get_start_time(dt_util.utcnow())
    has_mean = attributes["state_class"] == "measurement"
    mean_type = StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE
    has_sum = not has_mean

    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == []

    hass.states.async_set(
        "sensor.test", 10, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": statistics_unit,
            "has_mean": has_mean,
            "mean_type": mean_type,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": statistics_unit,
            "unit_class": unit_class,
        }
    ]

    # Change the state unit
    hass.states.async_set(
        "sensor.test", 10, attributes=attributes2, timestamp=now.timestamp()
    )

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": display_unit,
            "has_mean": has_mean,
            "mean_type": mean_type,
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

    async def assert_validation_result(client, expected_result):
        await client.send_json_auto_id({"type": "recorder/validate_statistics"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected_result

    # No statistics, no state - empty response
    client = await hass_ws_client()
    await assert_validation_result(client, {})


async def test_update_statistics_issues(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test update_statistics_issues can be called."""

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "recorder/update_statistics_issues"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None


async def test_clear_statistics(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing statistics."""
    now = get_start_time(dt_util.utcnow())

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES
    state = 10
    value = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test1", state, attributes=attributes, timestamp=now.timestamp()
    )
    hass.states.async_set(
        "sensor.test2", state * 2, attributes=attributes, timestamp=now.timestamp()
    )
    hass.states.async_set(
        "sensor.test3", state * 3, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "recorder/statistics_during_period",
            "statistic_ids": ["sensor.test1", "sensor.test2", "sensor.test3"],
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == expected_response

    await client.send_json_auto_id(
        {
            "type": "recorder/clear_statistics",
            "statistic_ids": ["sensor.test1", "sensor.test3"],
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "recorder/statistics_during_period",
            "statistic_ids": ["sensor.test1", "sensor.test2", "sensor.test3"],
            "start_time": now.isoformat(),
            "period": "5minute",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {"sensor.test2": expected_response["sensor.test2"]}


async def test_clear_statistics_time_out(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test removing statistics with time-out error."""
    client = await hass_ws_client()

    with (
        patch.object(recorder.tasks.ClearStatisticsTask, "run"),
        patch.object(recorder.websocket_api, "CLEAR_STATISTICS_TIME_OUT", 0),
    ):
        await client.send_json_auto_id(
            {
                "type": "recorder/clear_statistics",
                "statistic_ids": ["sensor.test"],
            }
        )
        response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "timeout",
        "message": "clear_statistics timed out",
    }


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
    now = get_start_time(dt_util.utcnow())

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test", state, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kW",
            "unit_class": "power",
        }
    ]

    await client.send_json_auto_id(
        {
            "type": "recorder/update_statistics_metadata",
            "statistic_id": "sensor.test",
            "unit_of_measurement": new_unit,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": new_display_unit,
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": new_unit,
            "unit_class": new_unit_class,
        }
    ]

    await client.send_json_auto_id(
        {
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


async def test_update_statistics_metadata_time_out(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test update statistics metadata with time-out error."""
    client = await hass_ws_client()

    with (
        patch.object(recorder.tasks.UpdateStatisticsMetadataTask, "run"),
        patch.object(recorder.websocket_api, "UPDATE_STATISTICS_METADATA_TIME_OUT", 0),
    ):
        await client.send_json_auto_id(
            {
                "type": "recorder/update_statistics_metadata",
                "statistic_id": "sensor.test",
                "unit_of_measurement": "dogs",
            }
        )
        response = await client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "timeout",
        "message": "update_statistics_metadata timed out",
    }


async def test_change_statistics_unit(
    recorder_mock: Recorder, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test change unit of recorded statistics."""
    now = get_start_time(dt_util.utcnow())

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)
    hass.states.async_set(
        "sensor.test", state, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "kW",
            "unit_class": "power",
        }
    ]

    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "new_unit_of_measurement": "W",
            "old_unit_of_measurement": "kW",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
            "has_sum": False,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": "W",
            "unit_class": "power",
        }
    ]

    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
            "type": "recorder/change_statistics_unit",
            "statistic_id": "sensor.test",
            "new_unit_of_measurement": "W",
            "old_unit_of_measurement": "W",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    await async_recorder_block_till_done(hass)

    await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
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
    now = get_start_time(dt_util.utcnow())

    units = METRIC_SYSTEM
    attributes = POWER_SENSOR_KW_ATTRIBUTES | {"device_class": None}
    state = 10

    expected_statistic_ids = [
        {
            "statistic_id": "sensor.test",
            "display_unit_of_measurement": "kW",
            "has_mean": True,
            "mean_type": StatisticMeanType.ARITHMETIC,
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
        await client.send_json_auto_id({"type": "recorder/list_statistic_ids"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == expected

    async def assert_statistics(expected):
        await client.send_json_auto_id(
            {
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
    hass.states.async_set(
        "sensor.test", state, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    do_adhoc_statistics(hass, period="hourly", start=now)
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()

    await assert_statistic_ids(expected_statistic_ids)
    await assert_statistics(expected_statistics)

    # Try changing to an invalid unit
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id({"type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "backlog": 0,
        "db_in_default_location": False,  # We never use the default URL in tests
        "max_backlog": 65000,
        "migration_in_progress": False,
        "migration_is_live": False,
        "recording": True,
        "thread_running": True,
    }


@pytest.mark.parametrize(
    ("db_url", "db_in_default_location"),
    [
        ("sqlite:///{config_dir}/home-assistant_v2.db", True),
        ("sqlite:///{config_dir}/custom.db", False),
        ("mysql://root:root_password@127.0.0.1:3316/homeassistant-test", False),
    ],
)
async def test_recorder_info_default_url(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    db_url: str,
    db_in_default_location: bool,
) -> None:
    """Test getting recorder status."""
    client = await hass_ws_client()

    # Ensure there are no queued events
    await async_wait_recording_done(hass)

    with patch.object(
        recorder_mock, "db_url", db_url.format(config_dir=hass.config.config_dir)
    ):
        await client.send_json_auto_id({"type": "recorder/info"})
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {
            "backlog": 0,
            "db_in_default_location": db_in_default_location,
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

    await client.send_json_auto_id({"type": "recorder/info"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


async def test_recorder_info_bad_recorder_config(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting recorder status when recorder is not started."""
    config = {recorder.CONF_DB_URL: "sqlite://no_file", recorder.CONF_DB_RETRY_WAIT: 0}

    client = await hass_ws_client()

    with patch("homeassistant.components.recorder.migration._migrate_schema"):
        recorder_helper.async_initialize_recorder(hass)
        assert not await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN not in hass.config.components
    await hass.async_block_till_done()

    # Wait for recorder to shut down
    await hass.async_add_executor_job(recorder.get_instance(hass).join)

    await client.send_json_auto_id({"type": "recorder/info"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["recording"] is False
    assert response["result"]["thread_running"] is False


async def test_recorder_info_wait_database_connect(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Test getting recorder info waits for recorder database connection."""
    client = await hass_ws_client()

    recorder_helper.async_initialize_recorder(hass)
    await client.send_json_auto_id({"type": "recorder/info"})

    async with async_test_recorder(hass):
        response = await client.receive_json()
        assert response["success"]
        assert response["result"] == {
            "backlog": ANY,
            "db_in_default_location": False,
            "max_backlog": 65000,
            "migration_in_progress": False,
            "migration_is_live": False,
            "recording": True,
            "thread_running": True,
        }


async def test_recorder_info_migration_queue_exhausted(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    async_test_recorder: RecorderInstanceContextManager,
    instrument_migration: InstrumentedMigration,
) -> None:
    """Test getting recorder status when recorder queue is exhausted."""
    assert recorder.util.async_migration_in_progress(hass) is False

    with (
        patch(
            "homeassistant.components.recorder.core.create_engine",
            new=create_engine_test,
        ),
        patch.object(recorder.core, "MAX_QUEUE_BACKLOG_MIN_VALUE", 1),
        patch.object(
            recorder.core, "MIN_AVAILABLE_MEMORY_FOR_QUEUE_BACKLOG", sys.maxsize
        ),
    ):
        async with async_test_recorder(
            hass, wait_recorder=False, wait_recorder_setup=False
        ):
            await hass.async_add_executor_job(
                instrument_migration.migration_started.wait
            )
            assert recorder.util.async_migration_in_progress(hass) is True
            await async_wait_recorder(hass)
            hass.states.async_set("my.entity", "on", {})
            await hass.async_block_till_done()

            # Detect queue full
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=2))
            await hass.async_block_till_done()

            client = await hass_ws_client()

            # Check the status
            await client.send_json_auto_id({"type": "recorder/info"})
            response = await client.receive_json()
            assert response["success"]
            assert response["result"]["migration_in_progress"] is True
            assert response["result"]["recording"] is False
            assert response["result"]["thread_running"] is True

            # Let migration finish
            instrument_migration.migration_stall.set()
            await async_wait_recording_done(hass)

            # Check the status after migration finished
            await client.send_json_auto_id({"type": "recorder/info"})
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

    await client.send_json_auto_id({"type": "backup/start"})
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "unknown_command"


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
    now = get_start_time(dt_util.utcnow())
    has_mean = attributes["state_class"] == "measurement"
    mean_type = StatisticMeanType.ARITHMETIC if has_mean else StatisticMeanType.NONE
    has_sum = not has_mean

    hass.config.units = units
    await async_setup_component(hass, "sensor", {})
    await async_recorder_block_till_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "recorder/get_statistics_metadata"})
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

    await client.send_json_auto_id(
        {
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
            "mean_type": mean_type,
            "has_sum": has_sum,
            "name": "Total imported energy",
            "source": "test",
            "statistics_unit_of_measurement": unit,
            "unit_class": unit_class,
        }
    ]

    hass.states.async_set(
        "sensor.test", 10, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    hass.states.async_set(
        "sensor.test2", 10, attributes=attributes, timestamp=now.timestamp()
    )
    await async_wait_recording_done(hass)

    await client.send_json_auto_id(
        {
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
            "mean_type": mean_type,
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

    await client.send_json_auto_id(
        {
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
            "mean_type": mean_type,
            "has_sum": has_sum,
            "name": None,
            "source": "recorder",
            "statistics_unit_of_measurement": attributes["unit_of_measurement"],
            "unit_class": unit_class,
        }
    ]


@pytest.mark.parametrize(
    ("source", "statistic_id"),
    [
        ("test", "test:total_energy_import"),
        ("recorder", "sensor.total_energy_import"),
    ],
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

    await client.send_json_auto_id(
        {
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "mean_type": StatisticMeanType.NONE,
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
                "mean_type": StatisticMeanType.NONE,
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

    await client.send_json_auto_id(
        {
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

    await client.send_json_auto_id(
        {
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
    [
        ("test", "test:total_energy_import"),
        ("recorder", "sensor.total_energy_import"),
    ],
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

    await client.send_json_auto_id(
        {
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "mean_type": StatisticMeanType.NONE,
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
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }

    # Adjust previously inserted statistics in kWh
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    [
        ("test", "test:total_gas"),
        ("recorder", "sensor.total_gas"),
    ],
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

    await client.send_json_auto_id(
        {
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
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "m³",
            "has_mean": False,
            "mean_type": StatisticMeanType.NONE,
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
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "m³",
            },
        )
    }

    # Adjust previously inserted statistics in m³
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    [
        ("kWh", "kWh", "energy", 1, ("Wh", "kWh", "MWh"), ("ft³", "m³", "cats", None)),
        ("MWh", "MWh", "energy", 1, ("Wh", "kWh", "MWh"), ("ft³", "m³", "cats", None)),
        ("m³", "m³", "volume", 1, ("ft³", "m³"), ("Wh", "kWh", "MWh", "cats", None)),
        ("ft³", "ft³", "volume", 1, ("ft³", "m³"), ("Wh", "kWh", "MWh", "cats", None)),
        ("dogs", "dogs", None, 1, ("dogs",), ("cats", None)),
        (None, None, "unitless", 1, (None,), ("cats",)),
    ],
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

    await client.send_json_auto_id(
        {
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
            "mean_type": StatisticMeanType.NONE,
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
                "mean_type": StatisticMeanType.NONE,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": state_unit,
            },
        )
    }

    # Try to adjust statistics
    await client.send_json_auto_id(
        {
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
        await client.send_json_auto_id(
            {
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
        await client.send_json_auto_id(
            {
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


async def test_import_statistics_with_last_reset(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test importing external statistics with last_reset can be fetched via websocket api."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = dt_util.parse_datetime("2022-01-01T00:00:00+02:00")
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    external_statistics1 = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }
    external_statistics2 = {
        "start": period2,
        "last_reset": last_reset,
        "state": 1,
        "sum": 3,
    }

    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(
        hass, external_metadata, (external_statistics1, external_statistics2)
    )
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json_auto_id(
        {
            "type": "recorder/statistics_during_period",
            "start_time": zero.isoformat(),
            "end_time": (zero + timedelta(hours=48)).isoformat(),
            "statistic_ids": ["test:total_energy_import"],
            "period": "hour",
            "types": ["change", "last_reset", "max", "mean", "min", "state", "sum"],
        }
    )
    response = await client.receive_json()
    assert response["result"] == {
        "test:total_energy_import": [
            {
                "change": 2.0,
                "end": (period1.timestamp() * 1000) + (3600 * 1000),
                "last_reset": last_reset.timestamp() * 1000,
                "start": period1.timestamp() * 1000,
                "state": 0.0,
                "sum": 2.0,
            },
            {
                "change": 1.0,
                "end": (period2.timestamp() * 1000 + (3600 * 1000)),
                "last_reset": last_reset.timestamp() * 1000,
                "start": period2.timestamp() * 1000,
                "state": 1.0,
                "sum": 3.0,
            },
        ]
    }
