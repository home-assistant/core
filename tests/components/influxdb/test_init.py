"""The tests for the InfluxDB component."""

from dataclasses import dataclass
import datetime
from http import HTTPStatus
import logging
from unittest.mock import ANY, MagicMock, Mock, call, patch

import pytest

from homeassistant.components import influxdb
from homeassistant.components.influxdb.const import DEFAULT_BUCKET
from homeassistant.const import PERCENTAGE, STATE_OFF, STATE_ON, STATE_STANDBY
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.setup import async_setup_component

INFLUX_PATH = "homeassistant.components.influxdb"
INFLUX_CLIENT_PATH = f"{INFLUX_PATH}.InfluxDBClient"
BASE_V1_CONFIG = {}
BASE_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "organization": "org",
    "token": "token",
}


async def async_wait_for_queue_to_process(hass: HomeAssistant) -> None:
    """Wait for the queue to be processed.

    In the future we should refactor this away to not have
    to access hass.data directly.
    """
    await hass.async_add_executor_job(hass.data[influxdb.DOMAIN].block_till_done)


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


@pytest.fixture(autouse=True)
def mock_batch_timeout(hass, monkeypatch):
    """Mock the event bus listener and the batch timeout for tests."""
    monkeypatch.setattr(
        f"{INFLUX_PATH}.InfluxThread.batch_timeout",
        Mock(return_value=0),
    )


@pytest.fixture(name="mock_client")
def mock_client_fixture(request):
    """Patch the InfluxDBClient object with mock for version under test."""
    if request.param == influxdb.API_VERSION_2:
        client_target = f"{INFLUX_CLIENT_PATH}V2"
    else:
        client_target = INFLUX_CLIENT_PATH

    with patch(client_target) as client:
        yield client


@pytest.fixture(name="get_mock_call")
def get_mock_call_fixture(request):
    """Get version specific lambda to make write API call mock."""

    def v2_call(body, precision):
        data = {"bucket": DEFAULT_BUCKET, "record": body}

        if precision is not None:
            data["write_precision"] = precision

        return call(**data)

    if request.param == influxdb.API_VERSION_2:
        return lambda body, precision=None: v2_call(body, precision)
    # pylint: disable-next=unnecessary-lambda
    return lambda body, precision=None: call(body, time_precision=precision)


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            {
                "api_version": influxdb.DEFAULT_API_VERSION,
                "username": "user",
                "password": "password",
                "verify_ssl": "False",
            },
            _get_write_api_mock_v1,
        ),
        (
            influxdb.API_VERSION_2,
            {
                "api_version": influxdb.API_VERSION_2,
                "token": "token",
                "organization": "organization",
                "bucket": "bucket",
            },
            _get_write_api_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_setup_config_full(
    hass: HomeAssistant, mock_client, config_ext, get_write_api
) -> None:
    """Test the setup with full configuration."""
    config = {
        "influxdb": {
            "host": "host",
            "port": 123,
            "database": "db",
            "max_retries": 4,
            "ssl": "False",
        }
    }
    config["influxdb"].update(config_ext)

    assert await async_setup_component(hass, influxdb.DOMAIN, config)
    await hass.async_block_till_done()
    assert get_write_api(mock_client).call_count == 1


@pytest.mark.parametrize(
    ("mock_client", "config_base", "config_ext", "expected_client_args"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "ssl": True,
                "verify_ssl": False,
            },
            {
                "ssl": True,
                "verify_ssl": False,
            },
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "ssl": True,
                "verify_ssl": True,
            },
            {
                "ssl": True,
                "verify_ssl": True,
            },
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "ssl": True,
                "verify_ssl": True,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
            {
                "ssl": True,
                "verify_ssl": "fake/path/ca.pem",
            },
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "ssl": True,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
            {
                "ssl": True,
                "verify_ssl": "fake/path/ca.pem",
            },
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            {
                "ssl": True,
                "verify_ssl": False,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
            {
                "ssl": True,
                "verify_ssl": False,
            },
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            {
                "api_version": influxdb.API_VERSION_2,
                "verify_ssl": False,
            },
            {
                "verify_ssl": False,
            },
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            {
                "api_version": influxdb.API_VERSION_2,
                "verify_ssl": True,
            },
            {
                "verify_ssl": True,
            },
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            {
                "api_version": influxdb.API_VERSION_2,
                "verify_ssl": True,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
            {
                "verify_ssl": True,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            {
                "api_version": influxdb.API_VERSION_2,
                "verify_ssl": False,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
            {
                "verify_ssl": False,
                "ssl_ca_cert": "fake/path/ca.pem",
            },
        ),
    ],
    indirect=["mock_client"],
)
async def test_setup_config_ssl(
    hass: HomeAssistant, mock_client, config_base, config_ext, expected_client_args
) -> None:
    """Test the setup with various verify_ssl values."""
    config = {"influxdb": config_base.copy()}
    config["influxdb"].update(config_ext)

    with (
        patch("os.access", return_value=True),
        patch("os.path.isfile", return_value=True),
    ):
        assert await async_setup_component(hass, influxdb.DOMAIN, config)
        await hass.async_block_till_done()

        assert expected_client_args.items() <= mock_client.call_args.kwargs.items()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api"),
    [
        (influxdb.DEFAULT_API_VERSION, BASE_V1_CONFIG, _get_write_api_mock_v1),
        (influxdb.API_VERSION_2, BASE_V2_CONFIG, _get_write_api_mock_v2),
    ],
    indirect=["mock_client"],
)
async def test_setup_minimal_config(
    hass: HomeAssistant, mock_client, config_ext, get_write_api
) -> None:
    """Test the setup with minimal configuration and defaults."""
    config = {"influxdb": {}}
    config["influxdb"].update(config_ext)

    assert await async_setup_component(hass, influxdb.DOMAIN, config)
    await hass.async_block_till_done()
    assert get_write_api(mock_client).call_count == 1


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api"),
    [
        (influxdb.DEFAULT_API_VERSION, {"username": "user"}, _get_write_api_mock_v1),
        (
            influxdb.DEFAULT_API_VERSION,
            {"token": "token", "organization": "organization"},
            _get_write_api_mock_v1,
        ),
        (
            influxdb.API_VERSION_2,
            {"api_version": influxdb.API_VERSION_2},
            _get_write_api_mock_v2,
        ),
        (
            influxdb.API_VERSION_2,
            {"api_version": influxdb.API_VERSION_2, "organization": "organization"},
            _get_write_api_mock_v2,
        ),
        (
            influxdb.API_VERSION_2,
            {
                "api_version": influxdb.API_VERSION_2,
                "token": "token",
                "organization": "organization",
                "username": "user",
                "password": "pass",
            },
            _get_write_api_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_invalid_config(
    hass: HomeAssistant, mock_client, config_ext, get_write_api
) -> None:
    """Test the setup with invalid config or config options specified for wrong version."""
    config = {"influxdb": {}}
    config["influxdb"].update(config_ext)

    assert not await async_setup_component(hass, influxdb.DOMAIN, config)


async def _setup(hass, mock_influx_client, config_ext, get_write_api):
    """Prepare client for next test and return event handler method."""
    config = {
        "influxdb": {
            "host": "host",
            "exclude": {"entities": ["fake.excluded"], "domains": ["another_fake"]},
        }
    }
    config["influxdb"].update(config_ext)
    assert await async_setup_component(hass, influxdb.DOMAIN, config)
    await hass.async_block_till_done()
    # A call is made to the write API during setup to test the connection.
    # Therefore we reset the write API mock here before the test begins.
    get_write_api(mock_influx_client).reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    # map of HA State to valid influxdb [state, value] fields
    valid = {
        "1": [None, 1],
        "1.0": [None, 1.0],
        STATE_ON: [STATE_ON, 1],
        STATE_OFF: [STATE_OFF, 0],
        STATE_STANDBY: [STATE_STANDBY, None],
        "foo": ["foo", None],
    }
    for in_, out in valid.items():
        attrs = {
            "unit_of_measurement": "foobars",
            "longitude": "1.1",
            "latitude": "2.2",
            "battery_level": f"99{PERCENTAGE}",
            "temperature": "20c",
            "last_seen": "Last seen 23 minutes ago",
            "updated_at": datetime.datetime(2017, 1, 1, 0, 0),
            "multi_periods": "0.120.240.2023873",
        }
        body = [
            {
                "measurement": "foobars",
                "tags": {"domain": "fake", "entity_id": "entity_id"},
                "time": ANY,
                "fields": {
                    "longitude": 1.1,
                    "latitude": 2.2,
                    "battery_level_str": f"99{PERCENTAGE}",
                    "battery_level": 99.0,
                    "temperature_str": "20c",
                    "temperature": 20.0,
                    "last_seen_str": "Last seen 23 minutes ago",
                    "last_seen": 23.0,
                    "updated_at_str": "2017-01-01 00:00:00",
                    "updated_at": 20170101000000,
                    "multi_periods_str": "0.120.240.2023873",
                },
            }
        ]
        if out[0] is not None:
            body[0]["fields"]["state"] = out[0]
        if out[1] is not None:
            body[0]["fields"]["value"] = out[1]

        hass.states.async_set("fake.entity_id", in_, attrs)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_no_units(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener for missing units."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    for unit in ("",):
        if unit:
            attrs = {"unit_of_measurement": unit}
        else:
            attrs = {}
        body = [
            {
                "measurement": "fake.entity_id",
                "tags": {"domain": "fake", "entity_id": "entity_id"},
                "time": ANY,
                "fields": {"value": 1},
            }
        ]
        hass.states.async_set("fake.entity_id", 1, attrs)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_inf(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with large or invalid numbers."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    attrs = {"bignumstring": "9" * 999, "nonumstring": "nan"}
    body = [
        {
            "measurement": "fake.entity_id",
            "tags": {"domain": "fake", "entity_id": "entity_id"},
            "time": ANY,
            "fields": {"value": 8},
        }
    ]
    hass.states.async_set("fake.entity_id", 8, attrs)
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_states(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against ignored states."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    for state_state in (1, "unknown", "", "unavailable"):
        body = [
            {
                "measurement": "fake.entity_id",
                "tags": {"domain": "fake", "entity_id": "entity_id"},
                "time": ANY,
                "fields": {"value": 1},
            }
        ]
        hass.states.async_set("fake.entity_id", state_state)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        if state_state == 1:
            assert write_api.call_count == 1
            assert write_api.call_args == get_mock_call(body)
        else:
            assert not write_api.called
        write_api.reset_mock()


async def execute_filter_test(hass: HomeAssistant, tests, write_api, get_mock_call):
    """Execute all tests for a given filtering test."""
    for test in tests:
        domain, entity_id = split_entity_id(test.id)
        body = [
            {
                "measurement": test.id,
                "tags": {"domain": domain, "entity_id": entity_id},
                "time": ANY,
                "fields": {"value": 1},
            }
        ]
        hass.states.async_set(test.id, 1)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        if test.should_pass:
            write_api.assert_called_once()
            assert write_api.call_args == get_mock_call(body)
        else:
            assert not write_api.called
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_denylist(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a denylist."""
    config = {"exclude": {"entities": ["fake.denylisted"]}, "include": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("fake.denylisted", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_denylist_domain(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a domain denylist."""
    config = {"exclude": {"domains": ["another_fake"]}, "include": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.denylisted", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_denylist_glob(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a glob denylist."""
    config = {"exclude": {"entity_globs": ["*.excluded_*"]}, "include": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("fake.excluded_entity", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_allowlist(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against an allowlist."""
    config = {"include": {"entities": ["fake.included"]}, "exclude": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.included", True),
        FilterTest("fake.excluded", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_allowlist_domain(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a domain allowlist."""
    config = {"include": {"domains": ["fake"]}, "exclude": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.excluded", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_allowlist_glob(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a glob allowlist."""
    config = {"include": {"entity_globs": ["*.included_*"]}, "exclude": {}}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.included_entity", True),
        FilterTest("fake.denied", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_filtered_allowlist(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against an allowlist filtered by denylist."""
    config = {
        "include": {
            "domains": ["fake"],
            "entities": ["another_fake.included"],
            "entity_globs": "*.included_*",
        },
        "exclude": {
            "entities": ["fake.excluded"],
            "domains": ["another_fake"],
            "entity_globs": "*.excluded_*",
        },
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.included", True),
        FilterTest("test.included_entity", True),
        FilterTest("fake.excluded", False),
        FilterTest("another_fake.denied", False),
        FilterTest("fake.excluded_entity", False),
        FilterTest("another_fake.included_entity", True),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_filtered_denylist(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener against a domain/glob denylist with an entity id allowlist."""
    config = {
        "include": {"entities": ["another_fake.included", "fake.excluded_pass"]},
        "exclude": {"domains": ["another_fake"], "entity_globs": "*.excluded_*"},
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.included", True),
        FilterTest("fake.excluded_pass", True),
        FilterTest("another_fake.denied", False),
        FilterTest("fake.excluded_entity", False),
    ]
    await execute_filter_test(hass, tests, write_api, get_mock_call)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_invalid_type(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener when an attribute has an invalid type."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    # map of HA State to valid influxdb [state, value] fields
    valid = {
        "1": [None, 1],
        "1.0": [None, 1.0],
        STATE_ON: [STATE_ON, 1],
        STATE_OFF: [STATE_OFF, 0],
        STATE_STANDBY: [STATE_STANDBY, None],
        "foo": ["foo", None],
    }
    for in_, out in valid.items():
        attrs = {
            "unit_of_measurement": "foobars",
            "longitude": "1.1",
            "latitude": "2.2",
            "invalid_attribute": ["value1", "value2"],
        }
        body = [
            {
                "measurement": "foobars",
                "tags": {"domain": "fake", "entity_id": "entity_id"},
                "time": ANY,
                "fields": {
                    "longitude": 1.1,
                    "latitude": 2.2,
                    "invalid_attribute_str": "['value1', 'value2']",
                },
            }
        ]
        if out[0] is not None:
            body[0]["fields"]["state"] = out[0]
        if out[1] is not None:
            body[0]["fields"]["value"] = out[1]

        hass.states.async_set("fake.entity_id", in_, attrs)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_default_measurement(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with a default measurement."""
    config = {"default_measurement": "state"}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    body = [
        {
            "measurement": "state",
            "tags": {"domain": "fake", "entity_id": "ok"},
            "time": ANY,
            "fields": {"value": 1},
        }
    ]
    hass.states.async_set("fake.ok", 1)
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_unit_of_measurement_field(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener for unit of measurement field."""
    config = {"override_measurement": "state"}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    attrs = {"unit_of_measurement": "foobars"}
    body = [
        {
            "measurement": "state",
            "tags": {"domain": "fake", "entity_id": "entity_id"},
            "time": ANY,
            "fields": {"state": "foo", "unit_of_measurement_str": "foobars"},
        }
    ]
    hass.states.async_set("fake.entity_id", "foo", attrs)
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_tags_attributes(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener when some attributes should be tags."""
    config = {"tags_attributes": ["friendly_fake"]}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    attrs = {"friendly_fake": "tag_str", "field_fake": "field_str"}
    body = [
        {
            "measurement": "fake.something",
            "tags": {
                "domain": "fake",
                "entity_id": "something",
                "friendly_fake": "tag_str",
            },
            "time": ANY,
            "fields": {"value": 1, "field_fake_str": "field_str"},
        }
    ]
    hass.states.async_set("fake.something", 1, attrs)
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_component_override_measurement(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with overridden measurements."""
    config = {
        "component_config": {
            "sensor.fake_humidity": {"override_measurement": "humidity"}
        },
        "component_config_glob": {
            "binary_sensor.*motion": {"override_measurement": "motion"}
        },
        "component_config_domain": {"climate": {"override_measurement": "hvac"}},
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    test_components = [
        {"domain": "sensor", "id": "fake_humidity", "res": "humidity"},
        {"domain": "binary_sensor", "id": "fake_motion", "res": "motion"},
        {"domain": "climate", "id": "fake_thermostat", "res": "hvac"},
        {"domain": "other", "id": "just_fake", "res": "other.just_fake"},
    ]
    for comp in test_components:
        body = [
            {
                "measurement": comp["res"],
                "tags": {"domain": comp["domain"], "entity_id": comp["id"]},
                "time": ANY,
                "fields": {"value": 1},
            }
        ]
        hass.states.async_set(f"{comp['domain']}.{comp['id']}", 1)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_component_measurement_attr(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with a different measurement_attr."""
    config = {
        "measurement_attr": "domain__device_class",
        "component_config": {
            "sensor.fake_humidity": {"override_measurement": "humidity"}
        },
        "component_config_glob": {
            "binary_sensor.*motion": {"override_measurement": "motion"}
        },
        "component_config_domain": {"climate": {"override_measurement": "hvac"}},
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    test_components = [
        {
            "domain": "sensor",
            "id": "fake_temperature",
            "attrs": {"device_class": "humidity"},
            "res": "sensor__humidity",
        },
        {"domain": "sensor", "id": "fake_humidity", "attrs": {}, "res": "humidity"},
        {"domain": "binary_sensor", "id": "fake_motion", "attrs": {}, "res": "motion"},
        {"domain": "climate", "id": "fake_thermostat", "attrs": {}, "res": "hvac"},
        {"domain": "other", "id": "just_fake", "attrs": {}, "res": "other"},
    ]
    for comp in test_components:
        body = [
            {
                "measurement": comp["res"],
                "tags": {"domain": comp["domain"], "entity_id": comp["id"]},
                "time": ANY,
                "fields": {"value": 1},
            }
        ]
        hass.states.async_set(f"{comp['domain']}.{comp['id']}", 1, comp["attrs"])
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_ignore_attributes(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with overridden measurements."""
    config = {
        "ignore_attributes": ["ignore"],
        "component_config": {
            "sensor.fake_humidity": {"ignore_attributes": ["id_ignore"]}
        },
        "component_config_glob": {
            "binary_sensor.*motion": {"ignore_attributes": ["glob_ignore"]}
        },
        "component_config_domain": {
            "climate": {"ignore_attributes": ["domain_ignore"]}
        },
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    test_components = [
        {
            "domain": "sensor",
            "id": "fake_humidity",
            "attrs": {"glob_ignore": 1, "domain_ignore": 1},
        },
        {
            "domain": "binary_sensor",
            "id": "fake_motion",
            "attrs": {"id_ignore": 1, "domain_ignore": 1},
        },
        {
            "domain": "climate",
            "id": "fake_thermostat",
            "attrs": {"id_ignore": 1, "glob_ignore": 1},
        },
    ]
    for comp in test_components:
        entity_id = f"{comp['domain']}.{comp['id']}"
        fields = {"value": 1}
        fields.update(comp["attrs"])
        body = [
            {
                "measurement": entity_id,
                "tags": {"domain": comp["domain"], "entity_id": comp["id"]},
                "time": ANY,
                "fields": fields,
            }
        ]
        hass.states.async_set(
            entity_id,
            1,
            {
                "ignore": 1,
                "id_ignore": 1,
                "glob_ignore": 1,
                "domain_ignore": 1,
            },
        )
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_ignore_attributes_overlapping_entities(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener with overridden measurements."""
    config = {
        "component_config": {"sensor.fake": {"override_measurement": "units"}},
        "component_config_domain": {"sensor": {"ignore_attributes": ["ignore"]}},
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    body = [
        {
            "measurement": "units",
            "tags": {"domain": "sensor", "entity_id": "fake"},
            "time": ANY,
            "fields": {"value": 1},
        }
    ]
    hass.states.async_set("sensor.fake", 1, {"ignore": 1})
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)
    write_api.reset_mock()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_scheduled_write(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener retries after a write failure."""
    config = {"max_retries": 1}
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)
    write_api.side_effect = OSError("foo")

    # Write fails
    with patch.object(influxdb.time, "sleep") as mock_sleep:
        hass.states.async_set("entity.entity_id", 1)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)
        assert mock_sleep.called
    assert write_api.call_count == 2

    # Write works again
    write_api.side_effect = None
    with patch.object(influxdb.time, "sleep") as mock_sleep:
        hass.states.async_set("entity.entity_id", "2")
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)
        assert not mock_sleep.called
    assert write_api.call_count == 3


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_backlog_full(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener drops old events when backlog gets full."""
    await _setup(hass, mock_client, config_ext, get_write_api)

    monotonic_time = 0

    def fast_monotonic():
        """Monotonic time that ticks fast enough to cause a timeout."""
        nonlocal monotonic_time
        monotonic_time += 60
        return monotonic_time

    with patch("homeassistant.components.influxdb.time.monotonic", new=fast_monotonic):
        hass.states.async_set("entity.id", 1)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)

        assert get_write_api(mock_client).call_count == 0


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_event_listener_attribute_name_conflict(
    hass: HomeAssistant, mock_client, config_ext, get_write_api, get_mock_call
) -> None:
    """Test the event listener when an attribute conflicts with another field."""
    await _setup(hass, mock_client, config_ext, get_write_api)
    body = [
        {
            "measurement": "fake.something",
            "tags": {"domain": "fake", "entity_id": "something"},
            "time": ANY,
            "fields": {"value": 1, "value__str": "value_str"},
        }
    ]
    hass.states.async_set("fake.something", 1, {"value": "value_str"})
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call", "test_exception"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            ConnectionError("fail"),
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            influxdb.exceptions.InfluxDBClientError("fail"),
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            influxdb.exceptions.InfluxDBServerError("fail"),
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            ConnectionError("fail"),
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            influxdb.ApiException(http_resp=MagicMock()),
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_connection_failure_on_startup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    get_write_api,
    get_mock_call,
    test_exception,
) -> None:
    """Test the event listener when it fails to connect to Influx on startup."""
    write_api = get_write_api(mock_client)
    write_api.side_effect = test_exception
    config = {"influxdb": config_ext}

    with patch(f"{INFLUX_PATH}.event_helper") as event_helper:
        assert await async_setup_component(hass, influxdb.DOMAIN, config)
        await hass.async_block_till_done()

        assert (
            len([record for record in caplog.records if record.levelname == "ERROR"])
            == 1
        )
        event_helper.call_later.assert_called_once()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call", "test_exception"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            influxdb.exceptions.InfluxDBClientError(
                "fail", code=HTTPStatus.BAD_REQUEST
            ),
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            influxdb.ApiException(status=HTTPStatus.BAD_REQUEST, http_resp=MagicMock()),
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_invalid_inputs_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_client,
    config_ext,
    get_write_api,
    get_mock_call,
    test_exception,
) -> None:
    """Test the event listener when influx returns invalid inputs on write.

    The difference in error handling in this case is that we do not sleep
    and try again, if an input is invalid it is logged and dropped.

    Note that this shouldn't actually occur, if its possible for the current
    code to send an invalid input then it should be adjusted to stop that.
    But Influx is an external service so there may be edge cases that
    haven't been encountered yet.
    """
    await _setup(hass, mock_client, config_ext, get_write_api)

    write_api = get_write_api(mock_client)
    write_api.side_effect = test_exception

    log_emit_done = hass.loop.create_future()

    original_emit = caplog.handler.emit

    def wait_for_emit(record: logging.LogRecord) -> None:
        original_emit(record)
        if record.levelname == "ERROR":
            hass.loop.call_soon_threadsafe(log_emit_done.set_result, None)

    with (
        patch(f"{INFLUX_PATH}.time.sleep") as sleep,
        patch.object(caplog.handler, "emit", wait_for_emit),
    ):
        hass.states.async_set("fake.something", 1)
        await hass.async_block_till_done()
        await async_wait_for_queue_to_process(hass)
        await log_emit_done
        await hass.async_block_till_done()

        write_api.assert_called_once()
        assert (
            len([record for record in caplog.records if record.levelname == "ERROR"])
            == 1
        )
        sleep.assert_not_called()


@pytest.mark.parametrize(
    ("mock_client", "config_ext", "get_write_api", "get_mock_call", "precision"),
    [
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            "ns",
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            "ns",
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            "us",
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            "us",
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            "ms",
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            "ms",
        ),
        (
            influxdb.DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            influxdb.DEFAULT_API_VERSION,
            "s",
        ),
        (
            influxdb.API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            influxdb.API_VERSION_2,
            "s",
        ),
    ],
    indirect=["mock_client", "get_mock_call"],
)
async def test_precision(
    hass: HomeAssistant,
    mock_client,
    config_ext,
    get_write_api,
    get_mock_call,
    precision,
) -> None:
    """Test the precision setup."""
    config = {
        "precision": precision,
    }
    config.update(config_ext)
    await _setup(hass, mock_client, config, get_write_api)

    value = "1.9"
    body = [
        {
            "measurement": "foobars",
            "tags": {"domain": "fake", "entity_id": "entity_id"},
            "time": ANY,
            "fields": {"value": float(value)},
        }
    ]
    hass.states.async_set(
        "fake.entity_id",
        value,
        {
            "unit_of_measurement": "foobars",
        },
    )
    await hass.async_block_till_done()
    await async_wait_for_queue_to_process(hass)

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body, precision)
    write_api.reset_mock()
