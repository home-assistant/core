"""Test the influxdb config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
import pytest

from homeassistant import config_entries
from homeassistant.components.influxdb import (
    API_VERSION_2,
    DEFAULT_API_VERSION,
    DOMAIN,
    ApiException,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    BASE_V1_CONFIG,
    BASE_V2_CONFIG,
    INFLUX_CLIENT_PATH,
    _get_write_api_mock_v1,
    _get_write_api_mock_v2,
)


@pytest.fixture(name="mock_client")
def mock_client_fixture(
    request: pytest.FixtureRequest,
) -> Generator[MagicMock]:
    """Patch the InfluxDBClient object with mock for version under test."""
    if request.param == API_VERSION_2:
        client_target = f"{INFLUX_CLIENT_PATH}V2"
    else:
        client_target = INFLUX_CLIENT_PATH

    with patch(client_target) as client:
        yield client


@pytest.mark.parametrize(
    ("mock_client", "config_base", "config_url", "get_write_api"),
    [
        (
            DEFAULT_API_VERSION,
            {
                "url": "http://localhost:8086",
                "verify_ssl": False,
                "database": "home_assistant",
                "username": "user",
                "password": "pass",
            },
            {
                "host": "localhost",
                "port": 8086,
                "ssl": False,
                "path": "/",
            },
            _get_write_api_mock_v1,
        ),
        (
            DEFAULT_API_VERSION,
            {
                "url": "http://localhost:8086",
                "verify_ssl": False,
                "database": "home_assistant",
            },
            {
                "host": "localhost",
                "port": 8086,
                "ssl": False,
                "path": "/",
            },
            _get_write_api_mock_v1,
        ),
        (
            DEFAULT_API_VERSION,
            {
                "url": "https://influxdb.mydomain.com",
                "verify_ssl": True,
                "database": "home_assistant",
                "username": "user",
                "password": "pass",
            },
            {
                "host": "influxdb.mydomain.com",
                "port": 443,
                "ssl": True,
                "path": "/",
            },
            _get_write_api_mock_v1,
        ),
    ],
    indirect=["mock_client"],
)
async def test_setup_v1(
    hass: HomeAssistant, mock_client, config_base, config_url, get_write_api
) -> None:
    """Test we can setup an InfluxDB v1."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_version": "1.x"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_v1"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_base,
        )

    data = {
        "api_version": "1",
        "host": config_url["host"],
        "port": config_url["port"],
        "username": config_base.get("username"),
        "password": config_base.get("password"),
        "database": config_base["database"],
        "ssl": config_url["ssl"],
        "path": config_url["path"],
        "verify_ssl": config_base["verify_ssl"],
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{config_base['database']} ({config_url['host']})"
    assert result["data"] == data


@pytest.mark.parametrize(
    ("mock_client", "config_base", "get_write_api"),
    [
        (
            API_VERSION_2,
            {
                "url": "http://localhost:8086",
                "verify_ssl": True,
                "organization": "my_org",
                "bucket": "home_assistant",
                "token": "token",
            },
            _get_write_api_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_setup_v2(
    hass: HomeAssistant, mock_client, config_base, get_write_api
) -> None:
    """Test we can setup an InfluxDB v1."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"api_version": "2.x"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_v2"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config_base,
        )

    data = {
        "api_version": "2",
        "url": config_base["url"],
        "organization": config_base["organization"],
        "bucket": config_base.get("bucket"),
        "token": config_base.get("token"),
        "verify_ssl": config_base["verify_ssl"],
    }

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{config_base['bucket']} ({config_base['url']})"
    assert result["data"] == data


@pytest.mark.parametrize(
    ("mock_client", "config_base", "get_write_api", "db_name", "host"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            BASE_V1_CONFIG["database"],
            BASE_V1_CONFIG["host"],
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            BASE_V2_CONFIG["bucket"],
            BASE_V2_CONFIG["url"],
        ),
    ],
    indirect=["mock_client"],
)
async def test_import(
    hass: HomeAssistant, mock_client, config_base, get_write_api, db_name, host
) -> None:
    """Test we can import."""
    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config_base,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"{db_name} ({host})"
    assert result["data"] == config_base

    assert get_write_api(mock_client).call_count == 1


@pytest.mark.parametrize(
    ("mock_client", "config_base", "get_write_api", "test_exception", "reason"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            ConnectionError("fail"),
            "cannot_connect",
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            InfluxDBClientError("fail"),
            "cannot_connect",
        ),
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
            InfluxDBServerError("fail"),
            "cannot_connect",
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            ConnectionError("fail"),
            "cannot_connect",
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            ApiException(http_resp=MagicMock()),
            "invalid_auth_v2",
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
            Exception(),
            "unknown",
        ),
    ],
    indirect=["mock_client"],
)
async def test_import_connection_error(
    hass: HomeAssistant, mock_client, config_base, get_write_api, test_exception, reason
) -> None:
    """Test abort on connection error."""
    write_api = get_write_api(mock_client)
    write_api.side_effect = test_exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config_base,
    )

    assert result["type"] == "abort"
    assert result["reason"] == reason
