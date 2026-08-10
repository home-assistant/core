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

# ---------------------------------------------------------------------------
# USER FORM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_show_form_user_no_input_reopens_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    # Initialize the flow handler with the HomeAssistant instance
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.async_set_unique_id = AsyncMock()
    flow.hass = hass

    # Invoke the initial step of the flow without user input
    result = await flow.async_step_user(user_input=None)

    # Validate that the form is returned to the user
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"


async def test_async_step_user_mawaqit_exception(hass: HomeAssistant) -> None:
    """Test the user step handles MawaqitException as a connection error."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
        side_effect=MawaqitException,
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"]["base"] == CANNOT_CONNECT_TO_SERVER


@pytest.mark.asyncio
async def test_async_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test the user step handles connection errors correctly."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Create an instance of ClientConnectorError with mock arguments
    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()
    connection_error_instance = ClientConnectorError(mock_conn_key, mock_os_error)

    # Patching the methods used in the flow to simulate external interactions
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            side_effect=connection_error_instance,
        ),
    ):
        # Simulate user input to trigger the flow's logic
        result = await flow.async_step_user(
            {CONF_USERNAME: "testuser", CONF_PASSWORD: "testpass"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "user"
        errors = result.get("errors")
        assert errors is not None and errors["base"] == CANNOT_CONNECT_TO_SERVER


@pytest.mark.asyncio
async def test_async_step_user_invalid_credentials(hass: HomeAssistant) -> None:
    """Test the user step with invalid credentials."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Patch the credentials test to simulate a login failure
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
        return_value=False,
    ):
        # Simulate user input with incorrect credentials
        result = await flow.async_step_user(
            {CONF_USERNAME: "wronguser", CONF_PASSWORD: "wrongpass"}
        )

        # Validate that the error is correctly handled and reported
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors["base"] == WRONG_CREDENTIAL


@pytest.mark.asyncio
async def test_async_step_user_valid_credentials(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test the user step with valid credentials proceeds to mosques_coordinates."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Patch the credentials test to simulate a login success
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            return_value=MOCK_TOKEN,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            return_value=mock_mosques_search_api_wrapper,
        ),
    ):
        # Simulate user input with correct credentials
        result = await flow.async_step_user(
            {CONF_USERNAME: "correctuser", CONF_PASSWORD: "correctpass"}
        )

        # Validate that the next form is displayed (mosques form)
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "mosques_coordinates"


# ---------------------------------------------------------------------------
# USER FORM - token retrieval error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_user_get_token_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test the user step when get_mawaqit_api_token raises a connection error."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()
    connection_error_instance = ClientConnectorError(mock_conn_key, mock_os_error)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            side_effect=connection_error_instance,
        ),
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors["base"] == CANNOT_CONNECT_TO_SERVER


@pytest.mark.asyncio
async def test_async_step_user_get_token_returns_none(
    hass: HomeAssistant,
) -> None:
    """Test the user step when get_mawaqit_api_token returns None."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            return_value=None,
        ),
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors["base"] == CANNOT_CONNECT_TO_SERVER


# ---------------------------------------------------------------------------
# MOSQUES COORDINATES - error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates_bad_credentials(
    hass: HomeAssistant,
) -> None:
    """Test mosques_coordinates step with bad credentials."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        side_effect=BadCredentialsException,
    ):
        result = await flow.async_step_mosques_coordinates()

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "cannot_connect"


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test mosques_coordinates step with connection error."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        side_effect=ClientConnectorError(mock_conn_key, mock_os_error),
    ):
        result = await flow.async_step_mosques_coordinates()

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "cannot_connect"


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates_no_mosque_around(
    hass: HomeAssistant,
) -> None:
    """Test mosques_coordinates step with NoMosqueAround."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        side_effect=NoMosqueAround,
    ):
        result = await flow.async_step_mosques_coordinates()

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "no_mosque"


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates_empty_name_servers(
    hass: HomeAssistant,
) -> None:
    """Test mosques_coordinates step when API returns None."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Return mosques with no label/uuid (empty parse result)
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value=None,
    ):
        result = await flow.async_step_mosques_coordinates()

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "no_mosque"


# ---------------------------------------------------------------------------
# MOSQUES COORDINATES FORM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test the mosques coordinates step shows a form then creates an entry."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Pre-fill the token and Mock external dependencies
    with (
        patch.object(flow, "token", MOCK_TOKEN),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            return_value=mock_mosques_search_api_wrapper,
        ),
    ):
        # Call the mosques step
        result = await flow.async_step_mosques_coordinates()

        # Verify the form is displayed with correct mosques options
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert (
            "data_schema" in result
            and result["data_schema"] is not None
            and CONF_UUID in result["data_schema"].schema
        )

        mosque_uuid = mock_mosques_search_api_wrapper[0].uuid
        result = await flow.async_step_mosques_coordinates({CONF_UUID: mosque_uuid})

        # Verify the flow processes the selection correctly
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY

        assert "data" in result and result["data"][CONF_UUID] == mosque_uuid
