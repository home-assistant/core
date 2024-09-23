"""Test the WatchYourLAN config flow."""

from unittest.mock import AsyncMock, patch

from httpx import ConnectError
import pytest

from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry  # Import MockConfigEntry


@pytest.fixture(name="mock_watchyourlan_client")
def mock_watchyourlan_client_fixture():
    """Fixture to mock WatchYourLANClient."""
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient",
    ) as mock_client:
        instance = mock_client.return_value
        instance.get_all_hosts = AsyncMock(return_value={})
        yield instance


@pytest.mark.parametrize(
    ("user_input", "api_response", "side_effect", "expected_result", "expected_errors"),
    [
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            {"title": "WatchYourLAN", "url": "http://127.0.0.1:8840"},
            None,
            FlowResultType.CREATE_ENTRY,
            {},
        ),
        (
            {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
            None,
            ConnectError("test"),
            FlowResultType.FORM,
            {"base": "cannot_connect"},
        ),
        (
            {CONF_URL: "http://invalid-url", CONF_VERIFY_SSL: False},
            None,
            ConnectError("test"),
            FlowResultType.FORM,
            {"base": "cannot_connect"},
        ),
    ],
)
async def test_form(
    hass: HomeAssistant,
    user_input: dict,
    api_response: dict,
    side_effect: Exception | None,
    expected_result: FlowResultType,
    expected_errors: dict,
    mock_watchyourlan_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test different scenarios for the form."""
    # Initiate the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Check that the form is shown with no errors initially
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Set the mock's return value and side effect based on the test case
    mock_watchyourlan_client.get_all_hosts.return_value = api_response
    mock_watchyourlan_client.get_all_hosts.side_effect = side_effect

    # Provide the user input
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    await hass.async_block_till_done()

    # Ensure the form shows the expected errors
    assert result["type"] is expected_result
    assert result.get("errors", {}) == expected_errors

    if expected_result is FlowResultType.CREATE_ENTRY:
        # Ensure that the config entry is created with correct values
        assert result["title"] == "WatchYourLAN"
        assert result["data"] == {
            CONF_URL: user_input[CONF_URL],
            CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
        }
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_generic_exception(
    hass: HomeAssistant,
    mock_watchyourlan_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test handling an unexpected generic exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Simulate an unexpected generic exception during validation
    mock_watchyourlan_client.get_all_hosts.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://127.0.0.1:8840", CONF_VERIFY_SSL: False},
    )

    # Ensure the form shows the unknown error
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_watchyourlan_client: AsyncMock
) -> None:
    """Test if an already configured entry is detected and aborted."""

    # Create a mock config entry to simulate an existing entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_URL: "http://127.0.0.1:8840"},
        title="WatchYourLAN",
        unique_id="http://127.0.0.1:8840",  # The unique_id should match the CONF_URL to trigger the abort
    )
    mock_entry.add_to_hass(hass)

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
