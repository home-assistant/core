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

from . import (
    BASE_V1_CONFIG,
    BASE_V2_CONFIG,
    INFLUX_CLIENT_PATH,
    _get_write_api_mock_v1,
    _get_write_api_mock_v2,
)

from tests.common import MockConfigEntry


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
    ("mock_client", "config_base", "get_write_api"),
    [
        (
            DEFAULT_API_VERSION,
            BASE_V1_CONFIG,
            _get_write_api_mock_v1,
        ),
        (
            API_VERSION_2,
            BASE_V2_CONFIG,
            _get_write_api_mock_v2,
        ),
    ],
    indirect=["mock_client"],
)
async def test_import(
    hass: HomeAssistant, mock_client, config_base, get_write_api
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
    assert result["title"] == config_base["host"]
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
            "cannot_connect",
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


@pytest.mark.parametrize(
    "config_base",
    [
        BASE_V1_CONFIG,
        BASE_V2_CONFIG,
    ],
)
async def test_import_update(hass: HomeAssistant, config_base) -> None:
    """Test we can import and update the config."""
    config_ext = {
        "include": {
            "entities": ["another_fake.included", "fake.excluded_pass"],
            "entity_globs": [],
            "domains": [],
        },
        "exclude": {
            "domains": ["another_fake"],
            "entity_globs": ["*.excluded_*"],
            "entities": [],
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=config_base,
        unique_id=config_base["host"],
    )
    entry.add_to_hass(hass)

    config = config_base.copy()
    config.update(config_ext)

    with patch(
        "homeassistant.components.influxdb.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data == config
