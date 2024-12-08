"""Tests for the WatchYourLAN config flow."""

from unittest.mock import AsyncMock

from httpx import ConnectError
import pytest

from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("user_input", "api_response"),
    [
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            {"url": "http://127.0.0.1:8840"},
        ),
    ],
)
async def test_form_happy_flow(
    hass: HomeAssistant,
    user_input: dict,
    api_response: dict,
    mock_watchyourlan_client_fixture: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy flow for the form."""
    # Initiate the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Check that the form is shown with no errors initially
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Set the mock's return value
    mock_watchyourlan_client_fixture.get_all_hosts.return_value = api_response

    # Provide the user input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    # Ensure the config entry is created with correct values
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WatchYourLAN"
    assert result["data"] == {
        CONF_URL: user_input[CONF_URL],
        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("user_input", "side_effect", "expected_errors"),
    [
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            ConnectError("Connection error"),
            {"base": "cannot_connect"},
        ),
        (
            {CONF_URL: "http://invalid-url", CONF_VERIFY_SSL: False},
            ValueError("Invalid URL"),
            {"base": "unknown"},
        ),
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            Exception("Unexpected error"),
            {"base": "unknown"},
        ),
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            RuntimeError("Runtime error"),
            {"base": "unknown"},
        ),
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            ValueError("Value error"),
            {"base": "unknown"},
        ),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    user_input: dict,
    side_effect: Exception,
    expected_errors: dict,
    mock_watchyourlan_client_fixture: AsyncMock,
    mock_watchyourlan_hosts,
) -> None:
    """Test handling of connection errors and unexpected exceptions."""
    # Initiate the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Set the mock's side effect based on the test case
    mock_watchyourlan_client_fixture.get_all_hosts.side_effect = side_effect

    # Provide the user input and simulate the initial error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    # Ensure the form shows the expected errors
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_errors

    # Now patch the mock to return a successful response with the correct structure
    mock_watchyourlan_client_fixture.get_all_hosts.side_effect = None
    mock_watchyourlan_client_fixture.get_all_hosts.return_value = (
        mock_watchyourlan_hosts  # Use the fixture response
    )

    # Retry the configuration flow using the same flow_id
    retry_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],  # Use the same flow ID from the previous call
        user_input,
    )

    # Ensure the retry results in a config entry being created
    assert retry_result["type"] is FlowResultType.CREATE_ENTRY
    assert retry_result["title"] == "WatchYourLAN"
    assert retry_result["data"] == {
        CONF_URL: user_input[CONF_URL],
        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
    }


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,  # Reuse the fixture here
    mock_watchyourlan_client_fixture: AsyncMock,
) -> None:
    """Test if an already configured entry is detected and aborted."""
    # Initiate the config flow
    first_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Provide the user input that matches the already existing entry
    result = await hass.config_entries.flow.async_configure(
        first_result["flow_id"],
        {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
    )

    # Ensure the flow aborts because the entry already exists
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
