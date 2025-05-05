"""Tests for the Mawaqit integration's config flow in Home Assistant."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError
from mawaqit.consts import NoMosqueAround, NoMosqueFound
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.mawaqit import DOMAIN, config_flow
from homeassistant.components.mawaqit.const import (
    CANNOT_CONNECT_TO_SERVER,
    CONF_CALC_METHOD,
    CONF_SEARCH,
    CONF_TYPE_SEARCH,
    CONF_TYPE_SEARCH_COORDINATES,
    CONF_TYPE_SEARCH_KEYWORD,
    NO_MOSQUE_FOUND_KEYWORD,
    WRONG_CREDENTIAL,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_UUID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# ----- TEST SETUP ----- #


@pytest.fixture
async def config_entry_setup(hass: HomeAssistant):
    """Create a mock config entry for tests."""
    entry = MockConfigEntry(
        version=10,
        minor_version=1,
        domain=DOMAIN,
        title="MAWAQIT - Mosque1",
        data={
            "api_key": "TOKEN",
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "latitude": 32.87336,
            "longitude": -117.22743,
        },
        source=config_entries.SOURCE_USER,
    )

    entry.add_to_hass(hass)  # register the MockConfigEntry to Hass

    return entry


@pytest.fixture
async def mock_mosques_test_data():
    """Provide mock data for mosques."""
    mock_mosques = [
        {
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "name": "Mosque1",
            "type": "MOSQUE",
            "slug": "1-mosque",
            "latitude": 48,
            "longitude": 1,
            "jumua": None,
            "proximity": 1744,
            "label": "Mosque1-label",
            "localisation": "aaaaa bbbbb cccccc",
        },
        {
            "uuid": "bbbbb-cccccc-ddddd-0000",
            "name": "Mosque2-label",
            "type": "MOSQUE",
            "slug": "2-mosque",
            "latitude": 47,
            "longitude": 1,
            "jumua": None,
            "proximity": 20000,
            "label": "Mosque2-label",
            "localisation": "bbbbb cccccc ddddd",
        },
        {
            "uuid": "bbbbb-cccccc-ddddd-0001",
            "name": "Mosque3",
            "type": "MOSQUE",
            "slug": "2-mosque",
            "latitude": 47,
            "longitude": 1,
            "jumua": None,
            "proximity": 20000,
            "label": "Mosque3-label",
            "localisation": "bbbbb cccccc ddddd",
        },
    ]

    mocked_mosques_data = (
        [
            "Mosque1-label (1.74km)",
            "Mosque2-label (20.0km)",
            "Mosque3-label (20.0km)",
        ],  # name_servers
        [
            "aaaaa-bbbbb-cccccc-0000",
            "bbbbb-cccccc-ddddd-0000",
            "bbbbb-cccccc-ddddd-0001",
        ],  # uuid_servers
        ["Mosque1-label", "Mosque2-label", "Mosque3-label"],  # CALC_METHODS
    )

    return mock_mosques, mocked_mosques_data


@pytest.fixture
def mock_config_entry_mawaqit() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        version=10,
        minor_version=1,
        domain=DOMAIN,
        title="MAWAQIT - Mosque1",
        data={
            "api_key": "TOKEN",
            "uuid": "aaaaa-bbbbb-cccccc-0000",
            "latitude": 32.87336,
            "longitude": -117.22743,
        },
        source=config_entries.SOURCE_USER,
        unique_id="84fce612f5b8",
    )


# ----- USER FORM ----- #


@pytest.mark.asyncio
async def test_show_form_user_no_input_reopens_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    # Initialize the flow handler with the HomeAssistant instance
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.async_set_unique_id = AsyncMock()
    flow.hass = hass
    flow.store = None  # Explicitly setting store to None

    # Invoke the initial step of the flow without user input
    result = await flow.async_step_user(user_input=None)

    # Validate that the form is returned to the user
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "user"


@pytest.mark.asyncio
async def test_async_step_user_connection_error(hass: HomeAssistant) -> None:
    """Test the user step handles connection errors correctly."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Create an instance of ClientConnectorError with mock argum4ents
    mock_conn_key = MagicMock()
    mock_os_error = MagicMock()
    connection_error_instance = ClientConnectorError(mock_conn_key, mock_os_error)

    # Patching the methods used in the flow to simulate external interactions
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.test_credentials",
            side_effect=connection_error_instance,
        ),
    ):
        # Simulate user input to trigger the flow's logic
        result = await flow.async_step_user(
            {CONF_USERNAME: "testuser", CONF_PASSWORD: "testpass"}
        )

        # Check that the flow returns a form with an error message due to the connection error
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "user"

        errors = result.get("errors")
        assert errors is not None and "base" in errors
        assert errors["base"] == CANNOT_CONNECT_TO_SERVER


@pytest.mark.asyncio
async def test_async_step_user_invalid_credentials(hass: HomeAssistant) -> None:
    """Test the user step with invalid credentials."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Patch the credentials test to simulate a login failure
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.test_credentials",
        return_value=False,
    ):
        # Simulate user input with incorrect credentials
        result = await flow.async_step_user(
            {CONF_USERNAME: "wronguser", CONF_PASSWORD: "wrongpass"}
        )

        # Validate that the error is correctly handled and reported
        assert result.get("type") == data_entry_flow.FlowResultType.FORM

        errors = result.get("errors")
        assert errors is not None and "base" in errors
        assert errors["base"] == WRONG_CREDENTIAL


@pytest.mark.asyncio
async def test_async_step_user_valid_credentials(hass: HomeAssistant) -> None:
    """Test the user step with valid credentials."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    flow.async_set_unique_id = AsyncMock()

    # Patch the credentials test to simulate a login success
    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.test_credentials",
            return_value=True,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.get_mawaqit_api_token",
            return_value="MAWAQIT_API_TOKEN",
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


# ----- SEARCH METHOD SELECTION FORM ----- #


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
        # Simulate user input to trigger the flow's logic
        result = await flow.async_step_search_method(
            {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_COORDINATES}
        )

        # Check that the flow is aborted due to the lack of mosques nearby
        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "no_mosque"


@pytest.mark.asyncio
async def test_async_step_search_method_coordinate_valid(
    hass: HomeAssistant, mock_mosques_test_data
) -> None:
    """Test the search method selection step with coordinates search method and where neighbor mosques are found."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass
    mock_mosques, _ = mock_mosques_test_data
    # Patching the methods used in the flow to simulate external interactions
    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value=mock_mosques,
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
    """Test the search method selection step with keyword search choice and check if the flow proceeds to the keyword search form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method(
        {CONF_TYPE_SEARCH: CONF_TYPE_SEARCH_KEYWORD}
    )

    # Check that
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "keyword_search"


@pytest.mark.asyncio
async def test_async_step_search_method_input_None(hass: HomeAssistant) -> None:
    """Test the search method selection step with no input provided and check if the flow show again the search method selection form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method(None)

    # Check that
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "search_method"


@pytest.mark.asyncio
async def test_async_step_search_method_Input_UNKNOWN(hass: HomeAssistant) -> None:
    """Test the search method selection step with an unknown input provided and check if the flow show again the search method selection form."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Simulate user input to trigger the flow's logic
    result = await flow.async_step_search_method({CONF_TYPE_SEARCH: "UNKNOWN"})

    # Check that
    assert result.get("type") == data_entry_flow.FlowResultType.FORM
    assert result.get("step_id") == "search_method"


# ----- MOSQUES KEYWORD SEARCH FORM ----- #


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
    hass: HomeAssistant, mock_mosques_test_data
) -> None:
    """Test the keyword search step with a keyword provided."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_mosques, _ = mock_mosques_test_data

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
        return_value=mock_mosques,
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
    """Test the keyword search step with a keyword provided and no mosque was found."""

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
        assert errors is not None and "base" in errors
        assert errors["base"] == NO_MOSQUE_FOUND_KEYWORD


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword_new_keyword(
    hass: HomeAssistant, mock_mosques_test_data
) -> None:
    """Test the keyword search step with a keyword provided."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_mosques, _ = mock_mosques_test_data

    with (
        patch.object(flow, "previous_keyword_search", "previous_mosque_test_keyword"),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_by_keyword",
            return_value=mock_mosques,
        ),
    ):
        result = await flow.async_step_keyword_search(
            user_input={CONF_SEARCH: "new_mosque_test_keyword", CONF_UUID: "uuid1"}
        )
        assert result.get("type") == data_entry_flow.FlowResultType.FORM
        assert result.get("step_id") == "keyword_search"


@pytest.mark.asyncio
async def test_async_step_keyword_search_with_keyword_same_keyword(
    hass: HomeAssistant,
    mock_mosques_test_data,
) -> None:
    """Test the keyword search step with the same keyword provided before."""
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    mock_mosques, mocked_mosques_data = mock_mosques_test_data
    previous_keyword_search = "mosque_test_keyword"

    with (
        patch.object(flow, "previous_keyword_search", previous_keyword_search),
        patch.object(flow, "token", "MAWAQIT_API_TOKEN"),
        patch.object(flow, "mosques", mock_mosques),
    ):
        # Now simulate the user selecting a mosque and submitting the form
        # Assuming the user selects the first mosque
        mosque_uuid_label = mocked_mosques_data[0][0]
        mosque_uuid = mocked_mosques_data[1][0]  # uuid of the first mosque

        result = await flow.async_step_keyword_search(
            user_input={
                CONF_SEARCH: previous_keyword_search,
                CONF_UUID: mosque_uuid_label,
            }
        )

        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert "data" in result and result["data"][CONF_UUID] == mosque_uuid


# ----- MOSQUES COORDINATES FORM ----- #


@pytest.mark.asyncio
async def test_async_step_mosques_coordinates(
    hass: HomeAssistant, mock_mosques_test_data
) -> None:
    """Test the mosques step in the config flow."""
    mock_mosques, mocked_mosques_data = mock_mosques_test_data
    flow = config_flow.MawaqitPrayerFlowHandler()
    flow.hass = hass

    # Pre-fill the token and Mock external dependencies
    with (
        patch.object(flow, "token", "MAWAQIT_API_TOKEN"),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            return_value=mock_mosques,
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

        # Now simulate the user selecting a mosque and submitting the form
        # Assuming the user selects the first mosque
        mosque_uuid_label = mocked_mosques_data[0][0]
        mosque_uuid = mocked_mosques_data[1][0]  # uuid of the first mosque

        result = await flow.async_step_mosques_coordinates(
            {CONF_UUID: mosque_uuid_label}
        )

        # Verify the flow processes the selection correctly
        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY

        assert "data" in result and result["data"][CONF_UUID] == mosque_uuid


# ----- OPTION FLOW FORM ----- #


@pytest.mark.asyncio
async def test_async_get_options_flow(mock_config_entry_mawaqit) -> None:
    """Test the options flow is correctly instantiated with the config entry."""

    options_flow = config_flow.MawaqitPrayerFlowHandler.async_get_options_flow(
        mock_config_entry_mawaqit
    )

    # Verify that the result is an instance of the expected options flow handler
    assert isinstance(options_flow, config_flow.MawaqitPrayerOptionsFlowHandler)


@pytest.mark.asyncio
async def test_options_flow_valid_input(
    hass: HomeAssistant,
    config_entry_setup,
    mock_mosques_test_data,
) -> None:
    """Test the options flow with valid input."""
    mock_mosques, mocked_mosques_data = mock_mosques_test_data

    # Initialize the options flow
    optionFlow = hass.config_entries.options

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            return_value=mock_mosques,
        ),
    ):
        # show initial form
        result = await optionFlow.async_init(config_entry_setup.entry_id)

        # Simulate user input in the options flow , Assuming the user selects the first mosque
        mosque_uuid_label = mocked_mosques_data[0][1]
        # submit form with options
        result = await optionFlow.async_configure(
            result["flow_id"], user_input={CONF_CALC_METHOD: mosque_uuid_label}
        )

        assert result.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_options_flow_no_input_reopens_form(
    hass: HomeAssistant,
    config_entry_setup,
) -> None:
    """Test the options flow reopens the form when no input is provided."""

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value={},
    ):
        # show initial form
        result = await hass.config_entries.options.async_init(
            config_entry_setup.entry_id
        )

        # submit form with no user input
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=None
        )

        assert (
            result.get("type") == data_entry_flow.FlowResultType.FORM
        )  # Assert that a form is shown
        assert result.get("step_id") == "init"


@pytest.mark.asyncio
async def test_options_flow_no_input_error_reopens_form(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
) -> None:
    """Test the options flow reopens the form when no input is provided and an error occurs."""
    # MawaqitPrayerOptionsFlowHandler.

    mock_config_entry_mawaqit.add_to_hass(hass)  # register the MockConfigEntry to Hass

    with patch(
        "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
        return_value={},
    ):
        # Simulate the init step
        result = await hass.config_entries.options.async_init(
            mock_config_entry_mawaqit.entry_id, data=None
        )

        assert (
            result.get("type") == data_entry_flow.FlowResultType.FORM
        )  # Assert that a form is shown

        assert result.get("step_id") == "init"


@pytest.mark.asyncio
async def test_options_flow_step_init_no_mosque_around(
    hass: HomeAssistant,
    mock_config_entry_mawaqit: MockConfigEntry,
) -> None:
    """Test the options flow reopens the form when no input is provided and an error occurs."""

    mock_config_entry_mawaqit.add_to_hass(hass)  # register the MockConfigEntry to Hass

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.all_mosques_neighborhood",
            side_effect=NoMosqueAround,
        ),
    ):
        # Simulate the init step
        result = await hass.config_entries.options.async_init(
            mock_config_entry_mawaqit.entry_id, data=None
        )

        assert result.get("type") == data_entry_flow.FlowResultType.ABORT
        assert result.get("reason") == "no_mosque"
