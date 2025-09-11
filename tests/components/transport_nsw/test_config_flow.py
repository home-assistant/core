"""Test the Transport NSW config flow."""

from unittest.mock import patch

import pytest

from homeassistant.components.transport_nsw.config_flow import (
    TransportNSWConfigFlow,
    validate_subentry_input,
)
from homeassistant.components.transport_nsw.const import (
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# New main entry data (API key only)
MOCK_USER_DATA = {
    CONF_API_KEY: "test_api_key",
}

EXPECTED_CONFIG_DATA = {
    CONF_API_KEY: "test_api_key",
}

# Legacy test data for backward compatibility tests
MOCK_USER_DATA_LEGACY = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
}

EXPECTED_CONFIG_DATA_LEGACY = {
    CONF_API_KEY: "test_api_key",
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
    CONF_ROUTE: "",
    CONF_DESTINATION: "",
}

# Subentry test data
MOCK_SUBENTRY_DATA = {
    CONF_STOP_ID: "test_stop_id",
    CONF_NAME: "Test Stop",
    CONF_ROUTE: "T1",
    CONF_DESTINATION: "Test Destination",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        return_value={"title": "Transport NSW"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Transport NSW"
    assert result2["data"] == EXPECTED_CONFIG_DATA


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


# NOTE: The old test_form_multiple_stops_same_id is no longer relevant
# since multiple stops are now handled as subentries, not separate main entries


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
        unique_id="test_stop_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Updated Test Stop",
            CONF_ROUTE: "test_route",
            CONF_DESTINATION: "test_destination",
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_NAME: "Updated Test Stop",
        CONF_ROUTE: "test_route",
        CONF_DESTINATION: "test_destination",
    }


# Subentry flow tests
async def test_subentry_flow_creation(hass: HomeAssistant) -> None:
    """Test subentry flow creation."""
    # First create a main entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Test subentry creation
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_subentry_input",
        return_value={"title": "Test Stop"},
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            MOCK_SUBENTRY_DATA,
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Stop"
    assert result2["data"] == MOCK_SUBENTRY_DATA
    assert (
        result2["unique_id"] == f"{entry.entry_id}_{MOCK_SUBENTRY_DATA[CONF_STOP_ID]}"
    )


async def test_subentry_flow_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test subentry flow with invalid stop ID."""
    # First create a main entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Test subentry creation with invalid stop ID
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_subentry_input",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            MOCK_SUBENTRY_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_subentry_flow_reconfigure(hass: HomeAssistant) -> None:
    """Test subentry flow reconfiguration."""
    # First create a main entry with subentry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Create initial subentry
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_subentry_input",
        return_value={"title": "Test Stop"},
    ):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            MOCK_SUBENTRY_DATA,
        )

    # Get the created subentry
    subentry = list(entry.subentries.values())[0]

    # Test reconfiguration
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    updated_data = {**MOCK_SUBENTRY_DATA, CONF_NAME: "Updated Stop"}
    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_subentry_input",
        return_value={"title": "Updated Stop"},
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            updated_data,
        )

    # Reconfigure returns ABORT (successful update), not CREATE_ENTRY
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_subentry_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test subentry flow with unknown error."""
    # First create a main entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )
    entry.add_to_hass(hass)

    # Test subentry creation with unknown error
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_STOP), context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.transport_nsw.config_flow.validate_subentry_input",
        side_effect=Exception("Unknown error"),
    ):
        result2 = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            MOCK_SUBENTRY_DATA,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_async_get_supported_subentry_types(hass: HomeAssistant) -> None:
    """Test async_get_supported_subentry_types method."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=EXPECTED_CONFIG_DATA,
    )

    supported_types = TransportNSWConfigFlow.async_get_supported_subentry_types(entry)

    assert SUBENTRY_TYPE_STOP in supported_types
    assert len(supported_types) == 1


async def test_subentry_validation_with_api_key(hass: HomeAssistant) -> None:
    """Test subentry validation uses parent entry API key."""
    api_key = "test_api_key"
    data = MOCK_SUBENTRY_DATA

    with patch(
        "homeassistant.components.transport_nsw.config_flow.TransportNSW"
    ) as mock_transport:
        mock_instance = mock_transport.return_value
        mock_instance.get_departures.return_value = {"route": "T1", "due": 5}

        result = await validate_subentry_input(hass, api_key, data)

        # Should call API with correct parameters
        mock_instance.get_departures.assert_called_once_with(
            data[CONF_STOP_ID], data[CONF_ROUTE], data[CONF_DESTINATION], api_key
        )

        assert result["title"] == data[CONF_NAME]


async def test_subentry_validation_with_empty_name(hass: HomeAssistant) -> None:
    """Test subentry validation with empty name generates fallback."""
    api_key = "test_api_key"
    data = {**MOCK_SUBENTRY_DATA, CONF_NAME: ""}

    with patch(
        "homeassistant.components.transport_nsw.config_flow.TransportNSW"
    ) as mock_transport:
        mock_instance = mock_transport.return_value
        mock_instance.get_departures.return_value = {"route": "T1", "due": 5}

        result = await validate_subentry_input(hass, api_key, data)

        assert result["title"] == f"Stop {data[CONF_STOP_ID]}"


async def test_subentry_validation_api_error(hass: HomeAssistant) -> None:
    """Test subentry validation with API error."""
    api_key = "test_api_key"
    data = MOCK_SUBENTRY_DATA

    with patch(
        "homeassistant.components.transport_nsw.config_flow.TransportNSW"
    ) as mock_transport:
        mock_instance = mock_transport.return_value
        mock_instance.get_departures.side_effect = Exception("API Error")

        with pytest.raises(ValueError, match="Cannot connect to Transport NSW API"):
            await validate_subentry_input(hass, api_key, data)


async def test_subentry_validation_none_response(hass: HomeAssistant) -> None:
    """Test subentry validation with None API response."""
    api_key = "test_api_key"
    data = MOCK_SUBENTRY_DATA

    with patch(
        "homeassistant.components.transport_nsw.config_flow.TransportNSW"
    ) as mock_transport:
        mock_instance = mock_transport.return_value
        mock_instance.get_departures.return_value = None

        with pytest.raises(ValueError, match="Cannot connect to Transport NSW API"):
            await validate_subentry_input(hass, api_key, data)
