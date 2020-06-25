"""The tests for the InfluxDB component."""
from dataclasses import dataclass
import datetime

import pytest

import homeassistant.components.influxdb as influxdb
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    UNIT_PERCENTAGE,
)
from homeassistant.core import split_entity_id
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, Mock, call, patch

BASE_V1_CONFIG = {}
BASE_V2_CONFIG = {
    "api_version": influxdb.API_VERSION_2,
    "organization": "org",
    "token": "token",
}


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


@pytest.fixture(autouse=True)
def mock_batch_timeout(hass, monkeypatch):
    """Mock the event bus listener and the batch timeout for tests."""
    hass.bus.listen = MagicMock()
    monkeypatch.setattr(
        "homeassistant.components.influxdb.InfluxThread.batch_timeout",
        Mock(return_value=0),
    )


@pytest.fixture(name="mock_client")
def mock_client_fixture(request):
    """Patch the InfluxDBClient object with mock for version under test."""
    if request.param == influxdb.API_VERSION_2:
        client_target = "homeassistant.components.influxdb.InfluxDBClientV2"
    else:
        client_target = "homeassistant.components.influxdb.InfluxDBClient"

    with patch(client_target) as client:
        yield client


@pytest.fixture(name="get_mock_call")
def get_mock_call_fixture(request):
    """Get version specific lambda to make write API call mock."""
    if request.param == influxdb.API_VERSION_2:
        return lambda body: call(bucket=influxdb.DEFAULT_BUCKET, record=body)
    # pylint: disable=unnecessary-lambda
    return lambda body: call(body)


def _get_write_api_mock_v1(mock_influx_client):
    """Return the write api mock for the V1 client."""
    return mock_influx_client.return_value.write_points


def _get_write_api_mock_v2(mock_influx_client):
    """Return the write api mock for the V2 client."""
    return mock_influx_client.return_value.write_api.return_value.write


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api",
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
async def test_setup_config_full(hass, mock_client, config_ext, get_write_api):
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
    assert hass.bus.listen.called
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]
    assert get_write_api(mock_client).call_count == 1


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api",
    [
        (influxdb.DEFAULT_API_VERSION, BASE_V1_CONFIG, _get_write_api_mock_v1),
        (influxdb.API_VERSION_2, BASE_V2_CONFIG, _get_write_api_mock_v2),
    ],
    indirect=["mock_client"],
)
async def test_setup_minimal_config(hass, mock_client, config_ext, get_write_api):
    """Test the setup with minimal configuration and defaults."""
    config = {"influxdb": {}}
    config["influxdb"].update(config_ext)

    assert await async_setup_component(hass, influxdb.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.bus.listen.called
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]
    assert get_write_api(mock_client).call_count == 1


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api",
    [
        (influxdb.DEFAULT_API_VERSION, {"username": "user"}, _get_write_api_mock_v1),
        (influxdb.DEFAULT_API_VERSION, {"token": "token"}, _get_write_api_mock_v1),
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
async def test_invalid_config(hass, mock_client, config_ext, get_write_api):
    """Test the setup with invalid config or config options specified for wrong version."""
    config = {"influxdb": {}}
    config["influxdb"].update(config_ext)

    assert not await async_setup_component(hass, influxdb.DOMAIN, config)


async def _setup(hass, mock_influx_client, config_ext, get_write_api):
    """Prepare client for next test and return event handler method."""
    config = {
        "influxdb": {
            "host": "host",
            "exclude": {"entities": ["fake.blacklisted"], "domains": ["another_fake"]},
        }
    }
    config["influxdb"].update(config_ext)
    assert await async_setup_component(hass, influxdb.DOMAIN, config)
    await hass.async_block_till_done()
    # A call is made to the write API during setup to test the connection.
    # Therefore we reset the write API mock here before the test begins.
    get_write_api(mock_influx_client).reset_mock()
    return hass.bus.listen.call_args_list[0][0][1]


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

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
            "battery_level": f"99{UNIT_PERCENTAGE}",
            "temperature": "20c",
            "last_seen": "Last seen 23 minutes ago",
            "updated_at": datetime.datetime(2017, 1, 1, 0, 0),
            "multi_periods": "0.120.240.2023873",
        }
        state = MagicMock(
            state=in_,
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes=attrs,
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "foobars",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
                "fields": {
                    "longitude": 1.1,
                    "latitude": 2.2,
                    "battery_level_str": f"99{UNIT_PERCENTAGE}",
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

        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener for missing units."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

    for unit in (None, ""):
        if unit:
            attrs = {"unit_of_measurement": unit}
        else:
            attrs = {}
        state = MagicMock(
            state=1,
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes=attrs,
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "fake.entity-id",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
                "fields": {"value": 1},
            }
        ]
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener with large or invalid numbers."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

    attrs = {"bignumstring": "9" * 999, "nonumstring": "nan"}
    state = MagicMock(
        state=8,
        domain="fake",
        entity_id="fake.entity-id",
        object_id="entity",
        attributes=attrs,
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)
    body = [
        {
            "measurement": "fake.entity-id",
            "tags": {"domain": "fake", "entity_id": "entity"},
            "time": 12345,
            "fields": {"value": 8},
        }
    ]
    handler_method(event)
    hass.data[influxdb.DOMAIN].block_till_done()

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against ignored states."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

    for state_state in (1, "unknown", "", "unavailable"):
        state = MagicMock(
            state=state_state,
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes={},
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "fake.entity-id",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
                "fields": {"value": 1},
            }
        ]
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        write_api = get_write_api(mock_client)
        if state_state == 1:
            assert write_api.call_count == 1
            assert write_api.call_args == get_mock_call(body)
        else:
            assert not write_api.called
        write_api.reset_mock()


def execute_filter_test(hass, tests, handler_method, write_api, get_mock_call):
    """Execute all tests for a given filtering test."""
    for test in tests:
        domain, entity_id = split_entity_id(test.id)
        state = MagicMock(
            state=1,
            domain=domain,
            entity_id=test.id,
            object_id=entity_id,
            attributes={},
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": test.id,
                "tags": {"domain": domain, "entity_id": entity_id},
                "time": 12345,
                "fields": {"value": 1},
            }
        ]
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        if test.should_pass:
            write_api.assert_called_once()
            assert write_api.call_args == get_mock_call(body)
        else:
            assert not write_api.called
        write_api.reset_mock()


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a denylist."""
    config = {"exclude": {"entities": ["fake.denylisted"]}, "include": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("fake.denylisted", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a domain denylist."""
    config = {"exclude": {"domains": ["another_fake"]}, "include": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.denylisted", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a glob denylist."""
    config = {"exclude": {"entity_globs": ["*.excluded_*"]}, "include": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("fake.excluded_entity", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against an allowlist."""
    config = {"include": {"entities": ["fake.included"]}, "exclude": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.included", True),
        FilterTest("fake.excluded", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a domain allowlist."""
    config = {"include": {"domains": ["fake"]}, "exclude": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.excluded", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a glob allowlist."""
    config = {"include": {"entity_globs": ["*.included_*"]}, "exclude": {}}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.included_entity", True),
        FilterTest("fake.denied", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
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
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.included", True),
        FilterTest("test.included_entity", True),
        FilterTest("fake.excluded", False),
        FilterTest("another_fake.denied", False),
        FilterTest("fake.excluded_entity", False),
        FilterTest("another_fake.included_entity", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener against a domain/glob denylist with an entity id allowlist."""
    config = {
        "include": {"entities": ["another_fake.included", "fake.excluded_pass"]},
        "exclude": {"domains": ["another_fake"], "entity_globs": "*.excluded_*"},
    }
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)
    write_api = get_write_api(mock_client)

    tests = [
        FilterTest("fake.ok", True),
        FilterTest("another_fake.included", True),
        FilterTest("fake.excluded_pass", True),
        FilterTest("another_fake.denied", False),
        FilterTest("fake.excluded_entity", False),
    ]
    execute_filter_test(hass, tests, handler_method, write_api, get_mock_call)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener when an attribute has an invalid type."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

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
        state = MagicMock(
            state=in_,
            domain="fake",
            entity_id="fake.entity-id",
            object_id="entity",
            attributes=attrs,
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": "foobars",
                "tags": {"domain": "fake", "entity_id": "entity"},
                "time": 12345,
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

        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener with a default measurement."""
    config = {"default_measurement": "state"}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)

    state = MagicMock(
        state=1, domain="fake", entity_id="fake.ok", object_id="ok", attributes={},
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)
    body = [
        {
            "measurement": "state",
            "tags": {"domain": "fake", "entity_id": "ok"},
            "time": 12345,
            "fields": {"value": 1},
        }
    ]
    handler_method(event)
    hass.data[influxdb.DOMAIN].block_till_done()

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener for unit of measurement field."""
    config = {"override_measurement": "state"}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)

    attrs = {"unit_of_measurement": "foobars"}
    state = MagicMock(
        state="foo",
        domain="fake",
        entity_id="fake.entity-id",
        object_id="entity",
        attributes=attrs,
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)
    body = [
        {
            "measurement": "state",
            "tags": {"domain": "fake", "entity_id": "entity"},
            "time": 12345,
            "fields": {"state": "foo", "unit_of_measurement_str": "foobars"},
        }
    ]
    handler_method(event)
    hass.data[influxdb.DOMAIN].block_till_done()

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener when some attributes should be tags."""
    config = {"tags_attributes": ["friendly_fake"]}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)

    attrs = {"friendly_fake": "tag_str", "field_fake": "field_str"}
    state = MagicMock(
        state=1,
        domain="fake",
        entity_id="fake.something",
        object_id="something",
        attributes=attrs,
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)
    body = [
        {
            "measurement": "fake.something",
            "tags": {
                "domain": "fake",
                "entity_id": "something",
                "friendly_fake": "tag_str",
            },
            "time": 12345,
            "fields": {"value": 1, "field_fake_str": "field_str"},
        }
    ]
    handler_method(event)
    hass.data[influxdb.DOMAIN].block_till_done()

    write_api = get_write_api(mock_client)
    assert write_api.call_count == 1
    assert write_api.call_args == get_mock_call(body)


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
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
    handler_method = await _setup(hass, mock_client, config, get_write_api)

    test_components = [
        {"domain": "sensor", "id": "fake_humidity", "res": "humidity"},
        {"domain": "binary_sensor", "id": "fake_motion", "res": "motion"},
        {"domain": "climate", "id": "fake_thermostat", "res": "hvac"},
        {"domain": "other", "id": "just_fake", "res": "other.just_fake"},
    ]
    for comp in test_components:
        state = MagicMock(
            state=1,
            domain=comp["domain"],
            entity_id=f"{comp['domain']}.{comp['id']}",
            object_id=comp["id"],
            attributes={},
        )
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "measurement": comp["res"],
                "tags": {"domain": comp["domain"], "entity_id": comp["id"]},
                "time": 12345,
                "fields": {"value": 1},
            }
        ]
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        write_api = get_write_api(mock_client)
        assert write_api.call_count == 1
        assert write_api.call_args == get_mock_call(body)
        write_api.reset_mock()


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener retries after a write failure."""
    config = {"max_retries": 1}
    config.update(config_ext)
    handler_method = await _setup(hass, mock_client, config, get_write_api)

    state = MagicMock(
        state=1,
        domain="fake",
        entity_id="entity.id",
        object_id="entity",
        attributes={},
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)
    write_api = get_write_api(mock_client)
    write_api.side_effect = IOError("foo")

    # Write fails
    with patch.object(influxdb.time, "sleep") as mock_sleep:
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()
        assert mock_sleep.called
    assert write_api.call_count == 2

    # Write works again
    write_api.side_effect = None
    with patch.object(influxdb.time, "sleep") as mock_sleep:
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()
        assert not mock_sleep.called
    assert write_api.call_count == 3


@pytest.mark.parametrize(
    "mock_client, config_ext, get_write_api, get_mock_call",
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
    hass, mock_client, config_ext, get_write_api, get_mock_call
):
    """Test the event listener drops old events when backlog gets full."""
    handler_method = await _setup(hass, mock_client, config_ext, get_write_api)

    state = MagicMock(
        state=1,
        domain="fake",
        entity_id="entity.id",
        object_id="entity",
        attributes={},
    )
    event = MagicMock(data={"new_state": state}, time_fired=12345)

    monotonic_time = 0

    def fast_monotonic():
        """Monotonic time that ticks fast enough to cause a timeout."""
        nonlocal monotonic_time
        monotonic_time += 60
        return monotonic_time

    with patch("homeassistant.components.influxdb.time.monotonic", new=fast_monotonic):
        handler_method(event)
        hass.data[influxdb.DOMAIN].block_till_done()

        assert get_write_api(mock_client).call_count == 0
