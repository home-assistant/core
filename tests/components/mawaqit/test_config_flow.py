"""Tests for the Mawaqit integration's config flow in Home Assistant."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.exceptions import BadCredentialsException, MawaqitException, NoMosqueAround
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.mawaqit import config_flow
from homeassistant.components.mawaqit.const import (
    CANNOT_CONNECT_TO_SERVER,
    WRONG_CREDENTIAL,
)
from homeassistant.components.mawaqit.types import MawaqitMosqueData
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_UUID
from homeassistant.core import HomeAssistant

from .conftest import MOCK_TOKEN

USER_INPUT = {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a mocked AsyncMawaqitClient with a successful login."""
    client = MagicMock()
    client.token = MOCK_TOKEN
    client.get_api_token = AsyncMock(return_value=MOCK_TOKEN)
    client.all_mosques_neighborhood = AsyncMock(return_value=[])
    return client


def _flow(hass: HomeAssistant) -> config_flow.MawaqitPrayerFlowHandler:
    """Return a flow handler bound to hass."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    return flow


# ---------------------------------------------------------------------------
# USER FORM
# ---------------------------------------------------------------------------


async def test_show_form_user_no_input_reopens_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await _flow(hass).async_step_user(user_input=None)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (BadCredentialsException, WRONG_CREDENTIAL),
        (MawaqitException, CANNOT_CONNECT_TO_SERVER),
        (ConnectionError, CANNOT_CONNECT_TO_SERVER),
        (TimeoutError, CANNOT_CONNECT_TO_SERVER),
        (
            ClientConnectorError(MagicMock(), MagicMock()),
            CANNOT_CONNECT_TO_SERVER,
        ),
    ],
    ids=[
        "bad_credentials",
        "mawaqit_error",
        "connection_error",
        "timeout",
        "client_connector_error",
    ],
)
async def test_async_step_user_login_errors(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    expected_error: str,
) -> None:
    """Test the user step surfaces login failures as form errors."""
    mock_client.get_api_token.side_effect = side_effect

    with patch(
        "homeassistant.components.mawaqit.config_flow.AsyncMawaqitClient",
        return_value=mock_client,
    ):
        result = await _flow(hass).async_step_user(USER_INPUT)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"
    errors = result.get("errors")
    assert errors is not None and errors["base"] == expected_error


async def test_async_step_user_no_token_returned(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test the user step when the API returns no token."""
    mock_client.get_api_token.return_value = None

    with patch(
        "homeassistant.components.mawaqit.config_flow.AsyncMawaqitClient",
        return_value=mock_client,
    ):
        result = await _flow(hass).async_step_user(USER_INPUT)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    errors = result.get("errors")
    assert errors is not None and errors["base"] == CANNOT_CONNECT_TO_SERVER


async def test_async_step_user_valid_credentials(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
) -> None:
    """Test the user step with valid credentials proceeds to mosques_coordinates."""
    mock_client.all_mosques_neighborhood.return_value = mock_mosques_search_api_raw

    with patch(
        "homeassistant.components.mawaqit.config_flow.AsyncMawaqitClient",
        return_value=mock_client,
    ):
        result = await _flow(hass).async_step_user(USER_INPUT)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "mosques_coordinates"


async def test_async_step_user_creates_a_single_client(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
) -> None:
    """Test one client is built for the whole flow and reused for the search."""
    mock_client.all_mosques_neighborhood.return_value = mock_mosques_search_api_raw

    with patch(
        "homeassistant.components.mawaqit.config_flow.AsyncMawaqitClient",
        return_value=mock_client,
    ) as mock_client_class:
        await _flow(hass).async_step_user(USER_INPUT)

    mock_client_class.assert_called_once()
    mock_client.get_api_token.assert_awaited_once()
    mock_client.all_mosques_neighborhood.assert_awaited_once()


# ---------------------------------------------------------------------------
# MOSQUES COORDINATES - error paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        (NoMosqueAround, "no_mosque"),
        (BadCredentialsException, "cannot_connect"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (ClientConnectorError(MagicMock(), MagicMock()), "cannot_connect"),
    ],
    ids=[
        "no_mosque_around",
        "bad_credentials",
        "connection_error",
        "timeout",
        "client_connector_error",
    ],
)
async def test_async_step_mosques_coordinates_errors_abort(
    hass: HomeAssistant,
    mock_client: MagicMock,
    side_effect: Exception | type[Exception],
    expected_reason: str,
) -> None:
    """Test the mosques step aborts when the search fails."""
    mock_client.all_mosques_neighborhood.side_effect = side_effect

    flow = _flow(hass)
    flow.client = mock_client
    result = await flow.async_step_mosques_coordinates()

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == expected_reason


async def test_async_step_mosques_coordinates_no_mosque_found(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test the mosques step aborts when the search returns nothing."""
    flow = _flow(hass)
    flow.client = mock_client
    result = await flow.async_step_mosques_coordinates()

    assert result.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "no_mosque"


# ---------------------------------------------------------------------------
# MOSQUES COORDINATES FORM
# ---------------------------------------------------------------------------


async def test_async_step_mosques_coordinates(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_mosques_search_api_raw: list[dict],
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test the mosques coordinates step shows a form then creates an entry."""
    mock_client.all_mosques_neighborhood.return_value = mock_mosques_search_api_raw

    flow = _flow(hass)
    flow.client = mock_client

    result = await flow.async_step_mosques_coordinates()

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert (
        "data_schema" in result
        and result["data_schema"] is not None
        and CONF_UUID in result["data_schema"].schema
    )

    mosque_uuid = mock_mosques_search_api_wrapper[0].uuid
    result = await flow.async_step_mosques_coordinates({CONF_UUID: mosque_uuid})

    assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert "data" in result and result["data"][CONF_UUID] == mosque_uuid
