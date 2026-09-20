"""Define tests for the Airly config flow."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientConnectorError
from airly.exceptions import AirlyError
from airly.measurements import Measurement
import pytest

from homeassistant.components.airly.const import CONF_USE_NEAREST, DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 12.3,
    CONF_LONGITUDE: 45.6,
}


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airly.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


async def test_invalid_api_key(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
) -> None:
    """Test that errors are shown when API key is invalid."""
    point_measurements = (
        mock_airly_client.create_measurements_session_point.return_value
    )
    point_measurements.update.side_effect = AirlyError(
        HTTPStatus.UNAUTHORIZED, {"message": "Invalid authentication credentials"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["errors"] == {"base": "invalid_api_key"}

    point_measurements.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is False


async def test_invalid_location(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    mock_airly_measurements: Measurement,
    mock_airly_no_station_measurements: Measurement,
) -> None:
    """Test that errors are shown when location is invalid."""
    mock_airly_client.create_measurements_session_point.return_value.current = (
        mock_airly_no_station_measurements
    )
    mock_airly_client.create_measurements_session_nearest.return_value.update.side_effect = AirlyError(
        HTTPStatus.NOT_FOUND, {"message": "Installation was not found"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["errors"] == {"base": "wrong_location"}

    mock_airly_client.create_measurements_session_point.return_value.current = (
        mock_airly_measurements
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is False


async def test_invalid_location_for_point_and_nearest(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    mock_airly_no_station_measurements: Measurement,
) -> None:
    """Test an abort when the location is wrong for the point and nearest methods."""
    mock_airly_client.create_measurements_session_point.return_value.current = (
        mock_airly_no_station_measurements
    )
    mock_airly_client.create_measurements_session_nearest.return_value.current = (
        mock_airly_no_station_measurements
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_location"


async def test_duplicate_error(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
) -> None:
    """Test that errors are shown when duplicates are added."""
    MockConfigEntry(domain=DOMAIN, unique_id="12.3-45.6", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_create_entry(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is False


async def test_create_entry_with_nearest_method(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    mock_airly_no_station_measurements: Measurement,
) -> None:
    """Test that the user step works with nearest method."""
    mock_airly_client.create_measurements_session_point.return_value.current = (
        mock_airly_no_station_measurements
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
    assert result["data"][CONF_USE_NEAREST] is True


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (TimeoutError, "cannot_connect"),
        (ClientConnectorError(Mock(), OSError("test")), "cannot_connect"),
    ],
)
async def test_cannot_connect(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test that cannot_connect error is shown when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    point_measurements = (
        mock_airly_client.create_measurements_session_point.return_value
    )
    point_measurements.update.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["errors"] == {"base": error}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    point_measurements.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Exception("unexpected"), "unknown"),
        (
            AirlyError(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Server error"}),
            "unknown",
        ),
    ],
)
async def test_unknown_error(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test that unknown error is shown for unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    point_measurements = (
        mock_airly_client.create_measurements_session_point.return_value
    )
    point_measurements.update.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["errors"] == {"base": error}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    point_measurements.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
) -> None:
    """Test starting a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
    assert mock_config_entry.data[CONF_LATITUDE] == 12.3
    assert mock_config_entry.data[CONF_LONGITUDE] == 45.6
    mock_airly_client.create_measurements_session_point.assert_called_once_with(
        latitude=12.3, longitude=45.6
    )


async def test_reauth_with_nearest_method(
    hass: HomeAssistant,
    mock_airly_client: MagicMock,
) -> None:
    """Test that reauthentication validates the API key with the nearest method."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="12.3-45.6",
        data={**CONFIG, CONF_USE_NEAREST: True},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new_api_key"
    mock_airly_client.create_measurements_session_nearest.assert_called_once_with(
        latitude=12.3, longitude=45.6, max_distance_km=5
    )
    mock_airly_client.create_measurements_session_point.assert_not_called()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (
            AirlyError(
                HTTPStatus.UNAUTHORIZED,
                {"message": "Invalid authentication credentials"},
            ),
            "invalid_api_key",
        ),
        (
            AirlyError(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "Server error"}),
            "unknown",
        ),
        (TimeoutError, "cannot_connect"),
        (ClientConnectorError(Mock(), OSError("test")), "cannot_connect"),
        (Exception("unexpected"), "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airly_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    point_measurements = (
        mock_airly_client.create_measurements_session_point.return_value
    )
    point_measurements.update.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data[CONF_API_KEY] == "foo"

    point_measurements.update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_api_key"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"
