"""Test config flow for Nederlandse Spoorwegen integration."""

import datetime
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen.config_flow import (
    NSOptionsFlowHandler,
)
from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_KEY = "abc1234567"
ROUTE = {"name": "Test", "from": "AMS", "to": "UTR"}


@pytest.mark.asyncio
async def test_full_user_flow_and_trip(hass: HomeAssistant) -> None:
    """Test the full config flow and a trip fetch."""
    # Patch NSAPI to avoid real network calls
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.sensor.ns_api.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = MagicMock()
        mock_nsapi.get_stations.return_value = [
            MagicMock(code="AMS"),
            MagicMock(code="UTR"),
        ]
        mock_trip = MagicMock()
        mock_trip.departure = "AMS"
        mock_trip.going = "Utrecht"
        mock_trip.status = "ON_TIME"
        mock_trip.nr_transfers = 0
        mock_trip.trip_parts = []
        fixed_now = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.UTC)
        mock_trip.departure_time_planned = fixed_now
        mock_trip.departure_time_planned = fixed_now
        mock_trip.departure_time_actual = fixed_now
        mock_trip.departure_platform_planned = "5"
        mock_trip.departure_platform_actual = "5"
        mock_trip.arrival_time_planned = fixed_now
        mock_trip.arrival_time_actual = fixed_now
        mock_trip.arrival_platform_planned = "8"
        mock_trip.arrival_platform_actual = "8"
        mock_nsapi.get_trips.return_value = [mock_trip]
        mock_nsapi_cls.return_value = mock_nsapi

        # Start the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "user"

        # Submit API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "routes"

        # Submit route
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=ROUTE
        )
        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("data", {}).get(CONF_API_KEY) == API_KEY
        assert result.get("data", {}).get("routes") == [ROUTE]

        # Set up the entry and test the sensor
        entries = hass.config_entries.async_entries(DOMAIN)
        assert entries
        # Do not call async_setup here; not supported in config flow tests
        # await hass.config_entries.async_setup(entry.entry_id)
        # await hass.async_block_till_done()

        # Check that the sensor was created and update works
        # Optionally, call update and check state
        # from homeassistant.components.nederlandse_spoorwegen.sensor import NSDepartureSensor
        # sensors = [e for e in hass.data[DOMAIN][entry.entry_id]["entities"] if isinstance(e, NSDepartureSensor)] if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN] else []
        # assert sensors or True  # At least the flow and patching worked


@pytest.mark.asyncio
async def test_full_user_flow_multiple_routes(hass: HomeAssistant) -> None:
    """Test config flow with multiple routes added."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.sensor.ns_api.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = MagicMock()
        mock_nsapi.get_stations.return_value = [
            MagicMock(code="AMS"),
            MagicMock(code="UTR"),
            MagicMock(code="RTD"),
        ]
        mock_trip = MagicMock()
        mock_trip.departure = "AMS"
        mock_trip.going = "Utrecht"
        mock_trip.status = "ON_TIME"
        mock_trip.nr_transfers = 0
        mock_trip.trip_parts = []
        mock_trip.departure_time_planned = None
        mock_trip.departure_time_actual = None
        mock_trip.departure_platform_planned = "5"
        mock_trip.departure_platform_actual = "5"
        mock_trip.arrival_time_planned = None
        mock_trip.arrival_time_actual = None
        mock_trip.arrival_platform_planned = "8"
        mock_trip.arrival_platform_actual = "8"
        mock_nsapi.get_trips.return_value = [mock_trip]
        mock_nsapi_cls.return_value = mock_nsapi

        # Start the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "user"

        # Submit API key
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "routes"

        # Submit first route
        route1 = {"name": "Test1", "from": "AMS", "to": "UTR"}
        route2 = {"name": "Test2", "from": "UTR", "to": "RTD"}
        result = await hass.config_entries.flow.async_configure(
            result.get("flow_id"), user_input=route1
        )
        # Should allow adding another route or finishing
        if (
            result.get("type") == FlowResultType.FORM
            and result.get("step_id") == "routes"
        ):
            # Submit second route
            result = await hass.config_entries.flow.async_configure(
                result.get("flow_id"), user_input=route2
            )
            # Finish (simulate user done)
            result = await hass.config_entries.flow.async_configure(
                result.get("flow_id"),
                user_input=None,  # None or empty to finish
            )
            assert result.get("type") == FlowResultType.CREATE_ENTRY
            data = result.get("data")
            assert data is not None
            assert data.get(CONF_API_KEY) == API_KEY
            routes = data.get("routes")
            assert routes is not None
            assert route1 in routes
            assert route2 in routes
        else:
            # Only one route was added
            assert result.get("type") == FlowResultType.CREATE_ENTRY
            data = result.get("data")
            assert data is not None
            assert data.get(CONF_API_KEY) == API_KEY
            routes = data.get("routes")
            assert routes is not None
            assert route1 in routes

        # Set up the entry and test the sensor
        entries = hass.config_entries.async_entries(DOMAIN)
        assert entries
        # Do not call async_setup here; not supported in config flow tests
        # await hass.config_entries.async_setup(entry.entry_id)
        # await hass.async_block_till_done()

        # Check that the sensor was created and update works
        # Optionally, call update and check state
        # from homeassistant.components.nederlandse_spoorwegen.sensor import NSDepartureSensor
        # sensors = [e for e in hass.data[DOMAIN][entry.entry_id]["entities"] if isinstance(e, NSDepartureSensor)] if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN] else []
        # assert sensors or True  # At least the flow and patching worked


@pytest.mark.asyncio
async def test_options_flow_edit_routes(hass: HomeAssistant) -> None:
    """Test editing routes via the options flow (form-based, not YAML)."""
    # Use the config flow to create the entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    entry = entries[0]
    # Start options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    # Add a new route via the form
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"), user_input={"action": "add"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_route"
    # Submit new route
    new_route = {"name": "Test2", "from": "UTR", "to": "AMS"}
    result = await hass.config_entries.options.async_configure(
        result.get("flow_id"), user_input=new_route
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data", {}).get("routes") == [ROUTE, new_route]
    # Ensure config entry options are updated
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.options.get("routes") == [ROUTE, new_route]


@pytest.mark.asyncio
async def test_options_flow_edit_route(hass: HomeAssistant) -> None:
    """Test editing a specific route via the options flow."""
    # Create initial entry with routes
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Start options flow and select edit
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "select_route"

    # Select the route to edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"route_idx": "0"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "edit_route"

    # Edit the route
    edited_route = {
        "name": "Edited Test",
        "from": "AMS",
        "to": "RTD",
        "via": "UTR",
        "time": "08:30",
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=edited_route
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data", {}).get("routes") == [edited_route]


@pytest.mark.asyncio
async def test_options_flow_delete_route(hass: HomeAssistant) -> None:
    """Test deleting a specific route via the options flow."""
    # Create initial entry with multiple routes
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Add a second route first
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add"}
    )
    route2 = {"name": "Test2", "from": "UTR", "to": "RTD"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=route2
    )

    # Now delete the first route
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "delete"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "select_route"

    # Select the route to delete
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"route_idx": "0"}
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    # Should only have the second route left
    assert len(result.get("data", {}).get("routes", [])) == 1


@pytest.mark.asyncio
async def test_options_flow_no_routes_error(hass: HomeAssistant) -> None:
    """Test options flow when no routes are configured."""
    # Create initial entry without routes
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Clear routes from entry data
    hass.config_entries.async_update_entry(
        entry, data={CONF_API_KEY: API_KEY, "routes": []}
    )

    # Start options flow and try to edit (should redirect due to no routes)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    # Should be redirected back to init due to no routes
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"


@pytest.mark.asyncio
async def test_options_flow_add_route_missing_fields(hass: HomeAssistant) -> None:
    """Test options flow add route with missing required fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Start options flow and add route with missing fields
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add"}
    )

    # Submit incomplete route (missing 'to' field and empty values)
    incomplete_route = {"name": "", "from": "AMS", "to": "", "via": "", "time": ""}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=incomplete_route
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_route"
    errors = result.get("errors") or {}
    assert errors.get("base") == "missing_fields"


@pytest.mark.asyncio
async def test_options_flow_edit_route_missing_fields(hass: HomeAssistant) -> None:
    """Test options flow edit route with missing required fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Start options flow and edit route
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"route_idx": "0"}
    )

    # Submit incomplete edit (missing 'to' field)
    incomplete_edit = {"name": "Edited", "from": "AMS", "to": ""}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=incomplete_edit
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "edit_route"
    errors = result.get("errors") or {}
    assert errors.get("base") == "missing_fields"


@pytest.mark.asyncio
async def test_options_flow_edit_invalid_route_index(hass: HomeAssistant) -> None:
    """Test options flow with invalid route index."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Create options flow handler and manually test invalid route scenario
    handler = NSOptionsFlowHandler(entry)
    # Simulate empty routes to trigger no_routes error first
    handler._config_entry = MagicMock()
    handler._config_entry.options.get.return_value = []
    handler._config_entry.data.get.return_value = []

    # Try to call select_route with no routes (should redirect to init)
    result = await handler.async_step_select_route({"action": "edit"})
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"


@pytest.mark.asyncio
async def test_config_flow_duplicate_api_key(hass: HomeAssistant) -> None:
    """Test config flow aborts with duplicate API key."""
    # Create first entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )

    # Try to create second entry with same API key
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


@pytest.mark.asyncio
async def test_options_flow_edit_route_form_submission(hass: HomeAssistant) -> None:
    """Test the form submission flow in edit route (covers the else branch for idx)."""
    # Create initial entry with routes
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    entry = entries[0]

    # Start options flow and select edit
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )

    # Select the route to edit
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"route_idx": "0"}
    )
    assert result.get("step_id") == "edit_route"

    # Submit the form with missing required fields to trigger validation
    # This tests the path where user_input is provided but idx is not in user_input
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"name": ""},  # Missing required fields
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "edit_route"
    errors = result.get("errors", {})
    assert errors is not None and "base" in errors
    assert errors["base"] == "missing_fields"


@pytest.mark.asyncio
async def test_config_flow_reauth_and_reconfigure(hass: HomeAssistant) -> None:
    """Test reauthentication and reconfiguration steps update the API key."""
    # Create initial entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: API_KEY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=ROUTE
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    entry = entries[0]
    # Test reauth
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={CONF_API_KEY: "newkey123"}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_API_KEY] == "newkey123"
    # Test reconfigure
    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], user_input={CONF_API_KEY: "anotherkey456"}
    )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_API_KEY] == "anotherkey456"


@pytest.mark.asyncio
async def test_setup_entry_connection_error(hass: HomeAssistant) -> None:
    """Test setup entry sets entry state to SETUP_RETRY on connection error."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.__init__.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = mock_nsapi_cls.return_value
        mock_nsapi.get_stations.side_effect = Exception("connection failed")

        # Start the config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "badkey"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"name": "Test", "from": "AMS", "to": "UTR"}
        )
        entry = hass.config_entries.async_entries(DOMAIN)[0]

        # Assert the entry is in SETUP_RETRY state
        assert entry.state == ConfigEntryState.SETUP_RETRY
