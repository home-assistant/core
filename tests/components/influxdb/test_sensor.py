"""The tests for the InfluxDB sensor."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from datetime import timedelta
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from influxdb_client.rest import ApiException
import pytest
from voluptuous import Invalid

from homeassistant.components import sensor
from homeassistant.components.influxdb.const import (
    API_VERSION_2,
    DEFAULT_API_VERSION,
    DEFAULT_BUCKET,
    DEFAULT_DATABASE,
    DOMAIN,
    TEST_QUERY_V1,
    TEST_QUERY_V2,
)
from homeassistant.components.influxdb.sensor import PLATFORM_SCHEMA
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import PLATFORM_NOT_READY_BASE_WAIT_TIME
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed

INFLUXDB_PATH = "homeassistant.components.influxdb"
INFLUXDB_CLIENT_PATH = f"{INFLUXDB_PATH}.InfluxDBClient"
INFLUXDB_SENSOR_PATH = f"{INFLUXDB_PATH}.sensor"

BASE_V1_CONFIG = {}
BASE_V2_CONFIG = {
    "api_version": API_VERSION_2,
    "organization": "org",
    "token": "token",
}

BASE_V1_QUERY = {
    "queries": [
        {
            "name": "test",
            "unique_id": "unique_test_id",
            "measurement": "measurement",
            "where": "where",
            "field": "field",
        }
    ],
}
BASE_V2_QUERY = {
    "queries_flux": [
        {
            "name": "test",
            "unique_id": "unique_test_id",
            "query": "query",
        }
    ]
}


@dataclass
class Record:
    """Record in a Table."""

    values: dict


@dataclass
class Table:
    """Table in an Influx 2 resultset."""

    records: list[type[Record]]


@pytest.fixture(name="mock_client")
def mock_client_fixture(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Patch the InfluxDBClient object with mock for version under test."""
    if request.param == API_VERSION_2:
        client_target = f"{INFLUXDB_CLIENT_PATH}V2"
    else:
        client_target = INFLUXDB_CLIENT_PATH

    with patch(client_target) as client:
        yield client


@pytest.fixture(autouse=True, scope="module")
def mock_client_close():
    """Mock close method of clients at module scope."""
    with (
        patch(f"{INFLUXDB_CLIENT_PATH}.close") as close_v1,
        patch(f"{INFLUXDB_CLIENT_PATH}V2.close") as close_v2,
    ):
        yield (close_v1, close_v2)


def _make_v1_resultset(*args):
    """Create a mock V1 resultset."""
    for arg in args:
        yield {"value": arg}


def _make_v1_databases_resultset():
    """Create a mock V1 'show databases' resultset."""
    for name in (DEFAULT_DATABASE, "db2"):
        yield {"name": name}


def _make_v2_resultset(*args):
    """Create a mock V2 resultset."""
    tables = []

    for arg in args:
        values = {"_value": arg}
        record = Record(values)
        tables.append(Table([record]))

    return tables


def _make_v2_buckets_resultset():
    """Create a mock V2 'buckets()' resultset."""
    records = [Record({"name": name}) for name in (DEFAULT_BUCKET, "bucket2")]

    return [Table(records)]


def _set_query_mock_v1(
    mock_influx_client, return_value=None, query_exception=None, side_effect=None
):
    """Set return value or side effect for the V1 client."""
    query_api = mock_influx_client.return_value.query
    if side_effect:
        query_api.side_effect = side_effect

    else:
        if return_value is None:
            return_value = []

        def get_return_value(query, **kwargs):
            """Return mock for test query, return value otherwise."""
            if query == TEST_QUERY_V1:
                points = _make_v1_databases_resultset()
            else:
                if query_exception:
                    raise query_exception
                points = return_value

            query_output = MagicMock()
            query_output.get_points.return_value = points
            return query_output

        query_api.side_effect = get_return_value

    return query_api


def _set_query_mock_v2(
    mock_influx_client, return_value=None, query_exception=None, side_effect=None
):
    """Set return value or side effect for the V2 client."""
    query_api = mock_influx_client.return_value.query_api.return_value.query
    if side_effect:
        query_api.side_effect = side_effect
    else:
        if return_value is None:
            return_value = []

        def get_return_value(query):
            """Return buckets list for test query, return value otherwise."""
            if query == TEST_QUERY_V2:
                return _make_v2_buckets_resultset()

            if query_exception:
                raise query_exception

            return return_value

        query_api.side_effect = get_return_value

    return query_api


async def _setup(
    hass: HomeAssistant, config_ext, queries, expected_sensors
) -> list[State]:
    """Create client and test expected sensors."""
    config = {
        DOMAIN: config_ext,
        sensor.DOMAIN: {"platform": DOMAIN},
    }
    influx_config = config[sensor.DOMAIN]
    influx_config.update(config_ext)
    influx_config.update(queries)

    assert await async_setup_component(hass, sensor.DOMAIN, config)
    await hass.async_block_till_done()

    sensors = []
    for expected_sensor in expected_sensors:
        state = hass.states.get(expected_sensor)
        assert state is not None
        sensors.append(state)

    return sensors


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock"),
    [
        (DEFAULT_API_VERSION, BASE_V1_CONFIG, BASE_V1_QUERY, _set_query_mock_v1),
        (API_VERSION_2, BASE_V2_CONFIG, BASE_V2_QUERY, _set_query_mock_v2),
    ],
    indirect=["mock_client"],
)
async def test_minimal_config(
    hass: HomeAssistant, mock_client, config_ext, queries, set_query_mock
) -> None:
    """Test the minimal config and defaults."""
    set_query_mock(mock_client)
    await _setup(hass, config_ext, queries, ["sensor.test"])


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock"),
    [
        (
            DEFAULT_API_VERSION,
            {
                "ssl": "true",
                "host": "host",
                "port": "9000",
                "path": "path",
                "username": "user",
                "password": "pass",
                "database": "db",
                "verify_ssl": "true",
            },
            {
                "queries": [
                    {
                        "name": "test",
                        "unique_id": "unique_test_id",
                        "unit_of_measurement": "unit",
                        "measurement": "measurement",
                        "where": "where",
                        "value_template": "123",
                        "database": "db2",
                        "group_function": "fn",
                        "field": "field",
                    }
                ],
            },
            _set_query_mock_v1,
        ),
        (
            API_VERSION_2,
            {
                "api_version": "2",
                "ssl": "true",
                "host": "host",
                "port": "9000",
                "path": "path",
                "token": "token",
                "organization": "org",
                "bucket": "bucket",
            },
            {
                "queries_flux": [
                    {
                        "name": "test",
                        "unique_id": "unique_test_id",
                        "unit_of_measurement": "unit",
                        "range_start": "start",
                        "range_stop": "end",
                        "group_function": "fn",
                        "bucket": "bucket2",
                        "imports": "import",
                        "query": "query",
                    }
                ],
            },
            _set_query_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_full_config(
    hass: HomeAssistant, mock_client, config_ext, queries, set_query_mock
) -> None:
    """Test the full config."""
    set_query_mock(mock_client)
    await _setup(hass, config_ext, queries, ["sensor.test"])


@pytest.mark.parametrize("config_ext", [(BASE_V1_CONFIG), (BASE_V2_CONFIG)])
async def test_config_failure(hass: HomeAssistant, config_ext) -> None:
    """Test an invalid config."""
    config = {"platform": DOMAIN}
    config.update(config_ext)

    with pytest.raises(Invalid):
        PLATFORM_SCHEMA(config)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock", "make_resultset"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            _make_v1_resultset,
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            _make_v2_resultset,
        ),
    ],
    indirect=["mock_client"],
)
async def test_state_matches_query_result(
    hass: HomeAssistant,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
    make_resultset,
) -> None:
    """Test state of sensor matches response from query api."""
    set_query_mock(mock_client, return_value=make_resultset(42))

    sensors = await _setup(hass, config_ext, queries, ["sensor.test"])

    assert sensors[0].state == "42"


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock", "make_resultset"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            _make_v1_resultset,
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            _make_v2_resultset,
        ),
    ],
    indirect=["mock_client"],
)
async def test_state_matches_first_query_result_for_multiple_return(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
    make_resultset,
) -> None:
    """Test state of sensor matches response from query api."""
    set_query_mock(mock_client, return_value=make_resultset(42, "not used"))

    sensors = await _setup(hass, config_ext, queries, ["sensor.test"])
    assert sensors[0].state == "42"
    assert (
        len([record for record in caplog.records if record.levelname == "WARNING"]) == 1
    )


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
        ),
        (API_VERSION_2, BASE_V2_CONFIG, BASE_V2_QUERY, _set_query_mock_v2),
    ],
    indirect=["mock_client"],
)
async def test_state_for_no_results(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
) -> None:
    """Test state of sensor matches response from query api."""
    set_query_mock(mock_client)

    sensors = await _setup(hass, config_ext, queries, ["sensor.test"])
    assert sensors[0].state == STATE_UNKNOWN
    assert (
        len([record for record in caplog.records if record.levelname == "WARNING"]) == 1
    )


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock", "query_exception"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            OSError("fail"),
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            InfluxDBClientError("fail"),
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            InfluxDBClientError("fail", code=400),
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            OSError("fail"),
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            ApiException(http_resp=MagicMock()),
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            ApiException(status=HTTPStatus.BAD_REQUEST, http_resp=MagicMock()),
        ),
    ],
    indirect=["mock_client"],
)
async def test_error_querying_influx(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
    query_exception,
) -> None:
    """Test behavior of sensor when influx returns error."""
    set_query_mock(mock_client, query_exception=query_exception)

    sensors = await _setup(hass, config_ext, queries, ["sensor.test"])
    assert sensors[0].state == STATE_UNKNOWN
    assert (
        len([record for record in caplog.records if record.levelname == "ERROR"]) == 1
    )


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock", "make_resultset", "key"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "queries": [
                    {
                        "name": "test",
                        "unique_id": "unique_test_id",
                        "measurement": "measurement",
                        "where": "{{ illegal.template }}",
                        "field": "field",
                    }
                ]
            },
            _set_query_mock_v1,
            _make_v1_resultset,
            "where",
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            {
                "queries_flux": [
                    {
                        "name": "test",
                        "unique_id": "unique_test_id",
                        "query": "{{ illegal.template }}",
                    }
                ]
            },
            _set_query_mock_v2,
            _make_v2_resultset,
            "query",
        ),
    ],
    indirect=["mock_client"],
)
async def test_error_rendering_template(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
    make_resultset,
    key,
) -> None:
    """Test behavior of sensor with error rendering template."""
    set_query_mock(mock_client, return_value=make_resultset(42))

    sensors = await _setup(hass, config_ext, queries, ["sensor.test"])
    assert sensors[0].state == STATE_UNKNOWN
    assert (
        len(
            [
                record
                for record in caplog.records
                if record.levelname == "ERROR"
                and f"Could not render {key} template" in record.msg
            ]
        )
        == 1
    )


@pytest.mark.parametrize(
    (
        "mock_client",
        "config_ext",
        "queries",
        "set_query_mock",
        "test_exception",
        "make_resultset",
    ),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            OSError("fail"),
            _make_v1_resultset,
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            InfluxDBClientError("fail"),
            _make_v1_resultset,
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            BASE_V1_QUERY,
            _set_query_mock_v1,
            InfluxDBServerError("fail"),
            _make_v1_resultset,
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            OSError("fail"),
            _make_v2_resultset,
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            BASE_V2_QUERY,
            _set_query_mock_v2,
            ApiException(http_resp=MagicMock()),
            _make_v2_resultset,
        ),
    ],
    indirect=["mock_client"],
)
async def test_connection_error_at_startup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
    test_exception,
    make_resultset,
) -> None:
    """Test behavior of sensor when influx returns error."""
    query_api = set_query_mock(mock_client, side_effect=test_exception)
    expected_sensor = "sensor.test"

    # Test sensor is not setup first time due to connection error
    await _setup(hass, config_ext, queries, [])
    assert hass.states.get(expected_sensor) is None
    assert (
        len([record for record in caplog.records if record.levelname == "ERROR"]) == 1
    )

    # Stop throwing exception and advance time to test setup succeeds
    query_api.reset_mock(side_effect=True)
    set_query_mock(mock_client, return_value=make_resultset(42))
    new_time = dt_util.utcnow() + timedelta(seconds=PLATFORM_NOT_READY_BASE_WAIT_TIME)
    async_fire_time_changed(hass, new_time)
    await hass.async_block_till_done()
    assert hass.states.get(expected_sensor) is not None


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "queries", "set_query_mock"),
    [
        (
            DEFAULT_API_VERSION,
            {"database": "bad_db"},
            BASE_V1_QUERY,
            _set_query_mock_v1,
        ),
        (
            API_VERSION_2,
            {
                "api_version": API_VERSION_2,
                "organization": "org",
                "token": "token",
                "bucket": "bad_bucket",
            },
            BASE_V2_QUERY,
            _set_query_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_data_repository_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    queries,
    set_query_mock,
) -> None:
    """Test sensor is not setup when bucket not available."""
    set_query_mock(mock_client)
    await _setup(hass, config_ext, queries, [])
    assert hass.states.get("sensor.test") is None
    assert (
        len([record for record in caplog.records if record.levelname == "ERROR"]) == 1
    )
