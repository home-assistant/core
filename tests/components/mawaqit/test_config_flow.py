"""Tests for the Mawaqit integration's config flow in Home Assistant."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.exceptions import (
    BadCredentialsException,
    MawaqitException,
    NoMosqueAround,
    NoMosqueFound,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.mawaqit import config_flow
from homeassistant.components.mawaqit.const import (
    CANNOT_CONNECT_TO_SERVER,
    CONF_SEARCH,
    CONF_TYPE_SEARCH,
    CONF_TYPE_SEARCH_COORDINATES,
    CONF_TYPE_SEARCH_KEYWORD,
    KEYWORD_SEARCH_NEXT_PAGE,
    KEYWORD_SEARCH_PAGE_SIZE,
    KEYWORD_SEARCH_PREV_PAGE,
    NO_MOSQUE_FOUND_KEYWORD,
    WRONG_CREDENTIAL,
)
from homeassistant.components.mawaqit.types import MawaqitMosqueData
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, CONF_UUID
from homeassistant.core import HomeAssistant

from .conftest import MOCK_TOKEN

from tests.common import MockConfigEntry

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
async def test_async_step_user_valid_credentials(hass: HomeAssistant) -> None:
    """Test the user step with valid credentials proceeds to search_method."""
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
            return_value={},
        ),
    ):
        # Simulate user input with correct credentials
        result = await flow.async_step_user(
            {CONF_USERNAME: "correctuser", CONF_PASSWORD: "correctpass"}
        )

        # Validate that the next form is displayed (mosques form)
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "search_method"


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
# SEARCH METHOD - coordinate error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_search_method_coordinate_bad_credentials(
    hass: HomeAssistant,
) -> None:
    """Test search_method step with coordinates and bad credentials."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        side_effect=BadCredentialsException,
    ):
        result = await flow.async_step_search_method(
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "cannot_connect"


@pytest.mark.asyncio
async def test_async_step_search_method_coordinate_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test search_method step with coordinates and connection error."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        side_effect=ClientConnectorError(mock_conn_key, mock_os_error),
    ):
        result = await flow.async_step_search_method(
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "cannot_connect"


# ---------------------------------------------------------------------------
# KEYWORD SEARCH - error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_keyword_search_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test keyword search step with connection error."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        side_effect=ClientConnectorError(mock_conn_key, mock_os_error),
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "test_keyword"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors["base"] == CANNOT_CONNECT_TO_SERVER


@pytest.mark.asyncio
async def test_async_step_keyword_search_empty_name_servers(
    hass: HomeAssistant,
) -> None:
    """Test keyword search step when API returns an empty list."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Return empty list from API (not NoMosqueFound, but empty results)
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=[],
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "test_keyword"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        errors = result.get("errors")
        assert errors is not None and errors["base"] == NO_MOSQUE_FOUND_KEYWORD


# ---------------------------------------------------------------------------
# SEARCH METHOD SELECTION FORM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_search_method_coordinate_no_neighborhood(
    hass: HomeAssistant,
) -> None:
    """Test the search method selection step with coordinates search method and where no neighbor mosques are found."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Patching the methods used in the flow to simulate external interactions
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            side_effect=NoMosqueAround,
        ),
    ):
        result = await flow.async_step_search_method(
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES}
        )

        # Check that the flow is aborted due to the lack of mosques nearby
        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "no_mosque"


@pytest.mark.asyncio
async def test_async_step_search_method_coordinate_valid(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test coordinates path when nearby mosques are found."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Patching the methods used in the flow to simulate external interactions
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value=mock_mosques_search_api_wrapper,
    ):
        # Simulate user input to trigger the flow's logic
        result = await flow.async_step_search_method(
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES}
        )

        # Check that
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "mosques_coordinates"


@pytest.mark.asyncio
async def test_async_step_search_method_keyword(hass: HomeAssistant) -> None:
    """Test keyword path proceeds to keyword_search form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method(
        {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_KEYWORD}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"


@pytest.mark.asyncio
async def test_async_step_search_method_input_none(hass: HomeAssistant) -> None:
    """Test None input re-shows the search method selection form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method(None)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "search_method"


@pytest.mark.asyncio
async def test_async_step_search_method_input_unknown(hass: HomeAssistant) -> None:
    """Test unknown input re-shows the search method selection form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method({CONF_TYPE_SEARCH: "UNKNOWN"})

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "search_method"


# ---------------------------------------------------------------------------
# MOSQUES KEYWORD SEARCH FORM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_step_keyword_search_initial(hass: HomeAssistant) -> None:
    """Test the initial keyword search step with no user input."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_keyword_search(user_input=None)

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test keyword search with a keyword shows mosque results."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=mock_mosques_search_api_wrapper,
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "mosque_test_keyword"}
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "keyword_search"


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword_no_mosque_found(
    hass: HomeAssistant,
) -> None:
    """Test keyword search when no mosque is found."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        side_effect=NoMosqueFound,
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "mosque_test_keyword"}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "keyword_search"
        errors = result.get("errors")
        assert errors is not None and errors["base"] == NO_MOSQUE_FOUND_KEYWORD


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword_new_keyword(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test that a new keyword resets page to 1 and re-fetches."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with (
        patch.object(flow, "previous_keyword_search", "previous_mosque_test_keyword"),
        patch.object(flow, "keyword_page", 4),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
            return_value=mock_mosques_search_api_wrapper,
        ),
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "new_mosque_test_keyword", CONF_UUID: "uuid1"}
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "keyword_search"
        assert flow.keyword_page == 1


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword_same_keyword(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test that re-submitting the same keyword with a UUID creates an entry."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    previous_keyword_search = "mosque_test_keyword"

    with (
        patch.object(flow, "previous_keyword_search", previous_keyword_search),
        patch.object(flow, "token", "MAWAQIT_API_TOKEN"),
        patch.object(
            flow,
            "mosques",
            {mosque.uuid: mosque for mosque in mock_mosques_search_api_wrapper},
        ),
    ):
        # Now simulate the user selecting a mosque and submitting the form
        # Assuming the user selects the first mosque
        mosque_uuid = mock_mosques_search_api_wrapper[
            0
        ].uuid  # uuid of the first mosque

        result = await flow.async_step_keyword_search(
            user_input={
                CONF_SEARCH: previous_keyword_search,
                CONF_UUID: mosque_uuid,
            }
        )

        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert "data" in result and result["data"][CONF_UUID] == mosque_uuid


@pytest.mark.asyncio
async def test_async_step_keyword_search_next_page(
    hass: HomeAssistant,
) -> None:
    """Test that selecting next page increments the page and re-fetches."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.previous_keyword_search = "test"
    flow.keyword_page = 1

    full_page_mosques = [
        MawaqitMosqueData.from_dict(
            {
                "uuid": f"uuid-{i}",
                "name": f"Mosque{i}",
                "label": f"Mosque{i}-label",
                "proximity": 1000 * i,
                "longitude": 1,
                "latitude": 1,
            }
        )
        for i in range(KEYWORD_SEARCH_PAGE_SIZE)
    ]

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=full_page_mosques,
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "test", CONF_UUID: KEYWORD_SEARCH_NEXT_PAGE}
        )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"
    assert flow.keyword_page == 2


@pytest.mark.asyncio
async def test_async_step_keyword_search_prev_page(
    hass: HomeAssistant,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test that selecting previous page decrements the page and re-fetches."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    with (
        patch.object(flow, "previous_keyword_search", "test"),
        patch.object(flow, "keyword_page", 2),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
            return_value=mock_mosques_search_api_wrapper,
        ),
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "test", CONF_UUID: KEYWORD_SEARCH_PREV_PAGE}
        )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"
    assert flow.keyword_page == 1


@pytest.mark.asyncio
async def test_async_step_keyword_search_next_page_no_mosque_found_steps_back(
    hass: HomeAssistant,
) -> None:
    """Test that NoMosqueFound on page > 1 decrements the page back."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.previous_keyword_search = "test"
    flow.keyword_page = 2

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        side_effect=NoMosqueFound,
    ):
        result = await flow.async_step_keyword_search(user_input={CONF_SEARCH: "test"})

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"
    assert flow.keyword_page == 1  # stepped back
    errors = result.get("errors")
    assert errors is not None and errors["base"] == NO_MOSQUE_FOUND_KEYWORD


@pytest.mark.asyncio
async def test_async_step_keyword_search_next_page_empty_results_steps_back(
    hass: HomeAssistant,
) -> None:
    """Test that empty results on page > 1 decrements the page back."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.previous_keyword_search = "test"
    flow.keyword_page = 2

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=[],
    ):
        result = await flow.async_step_keyword_search(user_input={CONF_SEARCH: "test"})

    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"
    assert flow.keyword_page == 1  # stepped back
    errors = result.get("errors")
    assert errors is not None and errors["base"] == NO_MOSQUE_FOUND_KEYWORD


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


# ---------------------------------------------------------------------------
# RECONFIGURE FLOW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
async def test_async_step_reconfigure_sets_token_and_goes_to_search_method(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
) -> None:
    """Test that reconfigure reads the token from the existing entry."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "search_method"


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
async def test_async_step_reconfigure_coordinates_updates_entry(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test that reconfigure via coordinates calls async_update_reload_and_abort."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reconfigure_flow(hass)
    assert result["step_id"] == "search_method"

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value=mock_mosques_search_api_wrapper,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES},
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "mosques_coordinates"

    mosque = mock_mosques_search_api_wrapper[0]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_UUID: mosque.uuid}
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_mawaqit.data[CONF_UUID] == mosque.uuid


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
async def test_async_step_reconfigure_keyword_updates_entry(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
    mock_mosques_search_api_wrapper: list[MawaqitMosqueData],
) -> None:
    """Test that reconfigure via keyword search calls async_update_reload_and_abort, not create_entry."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reconfigure_flow(hass)
    assert result["step_id"] == "search_method"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_KEYWORD}
    )
    assert result["step_id"] == "keyword_search"

    mosque = mock_mosques_search_api_wrapper[0]

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=mock_mosques_search_api_wrapper,
    ):
        # First submit: provide keyword, get mosque list back
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SEARCH: "mosque_test_keyword"}
        )

    assert result["step_id"] == "keyword_search"

    # Second submit: same keyword + selected uuid
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SEARCH: "mosque_test_keyword", CONF_UUID: mosque.uuid},
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_mawaqit.data[CONF_UUID] == mosque.uuid


# ---------------------------------------------------------------------------
# RE-AUTH FLOW
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
async def test_async_step_reauth_shows_confirm_form(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
) -> None:
    """Test reauth starts and shows the confirmation form."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
async def test_async_step_reauth_confirm_success(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
) -> None:
    """Test successful reauthentication."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reauth_flow(hass)

    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            return_value="NEW_TOKEN",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
            },
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry_mawaqit.data[CONF_API_KEY] == "NEW_TOKEN"


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("validate_side_effect", "validate_return", "token_side_effect", "expected_error"),
    [
        # invalid credentials (no exception)
        (None, False, None, WRONG_CREDENTIAL),
        # validate_credentials connection errors
        (
            ClientConnectorError(MagicMock(), MagicMock()),
            None,
            None,
            CANNOT_CONNECT_TO_SERVER,
        ),
        (MawaqitException, None, None, CANNOT_CONNECT_TO_SERVER),
        # token retrieval connection errors
        (
            None,
            True,
            ClientConnectorError(MagicMock(), MagicMock()),
            CANNOT_CONNECT_TO_SERVER,
        ),
        (None, True, MawaqitException, CANNOT_CONNECT_TO_SERVER),
    ],
)
async def test_async_step_reauth_confirm_errors(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
    validate_side_effect,
    validate_return,
    token_side_effect,
    expected_error,
) -> None:
    """Test reauth failure paths."""
    mock_config_entry_mawaqit.add_to_hass(hass)

    result = await mock_config_entry_mawaqit.start_reauth_flow(hass)
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.validate_credentials",
            side_effect=validate_side_effect,
            return_value=validate_return,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            side_effect=token_side_effect,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    # Re-open the Auth flow and show the error
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == expected_error
