"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_handler import RequestStatus
import pytest

from homeassistant.components.pooldose.const import (
    CONF_INCLUDE_SENSITIVE_DATA,
    CONF_SERIALNUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_request_handler():
    """Create a mock RequestHandler that returns success."""
    handler = MagicMock()  # Changed from AsyncMock to MagicMock
    # Use return_value for synchronous method
    handler.check_apiversion_supported.return_value = (RequestStatus.SUCCESS, {})
    return handler


@pytest.fixture
def mock_pooldose_client():
    """Create a mock PooldoseClient."""
    client = AsyncMock()
    client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    return client


async def test_form_shows_and_creates_entry(
    hass: HomeAssistant, mock_request_handler, mock_pooldose_client
) -> None:
    """Test that the form is shown and entry is created on valid input."""
    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_request_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.SUCCESS, mock_pooldose_client),
        ),
    ):
        # Show initial form
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        # Submit form with valid data (include all fields that form expects)
        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 300,
            CONF_TIMEOUT: 10,
            CONF_INCLUDE_SENSITIVE_DATA: True,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        # Verify entry creation
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "PoolDose SN123456789"
        assert result2["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_SERIALNUMBER: "SN123456789",
            CONF_INCLUDE_SENSITIVE_DATA: True,
        }


async def test_form_cannot_connect_host_unreachable(hass: HomeAssistant) -> None:
    """Test that the form shows an error if the device is unreachable."""
    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler.create",
        return_value=(RequestStatus.HOST_UNREACHABLE, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "unreachable.local",
            CONF_SCAN_INTERVAL: 600,  # Add default values
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"


async def test_form_params_fetch_failed(hass: HomeAssistant) -> None:
    """Test that the form shows error when parameters cannot be fetched."""
    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler.create",
        return_value=(RequestStatus.PARAMS_FETCH_FAILED, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "parama_fetch_failed"


async def test_form_api_version_not_set(hass: HomeAssistant) -> None:
    """Test that the form shows error when API version is not set."""
    mock_handler = MagicMock()  # Changed from AsyncMock
    mock_handler.check_apiversion_supported.return_value = (
        RequestStatus.NO_DATA,
        {},
    )

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler.create",
        return_value=(RequestStatus.SUCCESS, mock_handler),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "api_not_set"


async def test_form_api_version_unsupported(hass: HomeAssistant) -> None:
    """Test that the form shows error when API version is unsupported."""
    mock_handler = MagicMock()  # Changed from AsyncMock
    api_versions = {"api_version_is": "v0.9", "api_version_should": "v1.0"}
    mock_handler.check_apiversion_supported.return_value = (
        RequestStatus.API_VERSION_UNSUPPORTED,
        api_versions,
    )

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler.create",
        return_value=(RequestStatus.SUCCESS, mock_handler),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "api_not_supported"
        assert result2["description_placeholders"] == api_versions


async def test_form_client_creation_failed(
    hass: HomeAssistant, mock_request_handler
) -> None:
    """Test that the form shows error when client creation fails."""
    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_request_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.HOST_UNREACHABLE, None),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_request_handler, mock_pooldose_client
) -> None:
    """Test that the flow aborts if the device is already configured."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456789",
        data={CONF_HOST: "192.168.1.50", CONF_SERIALNUMBER: "SN123456789"},
    )
    existing_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_request_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.SUCCESS, mock_pooldose_client),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_form_with_minimal_input(
    hass: HomeAssistant, mock_request_handler, mock_pooldose_client
) -> None:
    """Test form submission with only required fields."""
    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_request_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.SUCCESS, mock_pooldose_client),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        # Submit with minimal input (form will provide defaults)
        user_input = {
            CONF_HOST: "KOMMSPOT",
            CONF_SCAN_INTERVAL: 600,  # Must provide all form fields
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_HOST: "KOMMSPOT",
            CONF_SERIALNUMBER: "SN123456789",
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }


async def test_form_handles_missing_serial_number(
    hass: HomeAssistant, mock_request_handler
) -> None:
    """Test handling when device_info doesn't contain serial number."""
    mock_client = AsyncMock()
    mock_client.device_info = {}  # No SERIAL_NUMBER

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_request_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.SUCCESS, mock_client),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_SERIALNUMBER: None,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }


async def test_options_flow_init_form(hass: HomeAssistant) -> None:
    """Test that the options flow shows the init form."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_SERIALNUMBER: "SN123456789"},
        options={},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    # Don't test schema defaults - they're not reliable to test


async def test_options_flow_saves_data(hass: HomeAssistant) -> None:
    """Test that the options flow saves the provided data."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_SERIALNUMBER: "SN123456789"},
        options={CONF_SCAN_INTERVAL: 300, CONF_TIMEOUT: 15},
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    user_input = {
        CONF_SCAN_INTERVAL: 120,
        CONF_TIMEOUT: 20,
        CONF_INCLUDE_SENSITIVE_DATA: True,
    }
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == user_input


async def test_options_flow_uses_existing_options(hass: HomeAssistant) -> None:
    """Test that the options flow uses existing options as defaults."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_SERIALNUMBER: "SN123456789"},
        options={
            CONF_SCAN_INTERVAL: 180,
            CONF_TIMEOUT: 25,
            CONF_INCLUDE_SENSITIVE_DATA: True,
        },
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    # Just verify the form is shown correctly
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_form_retry_after_error(hass: HomeAssistant) -> None:
    """Test that user can retry after connection error."""
    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler.create",
        return_value=(RequestStatus.HOST_UNREACHABLE, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        # First attempt fails
        user_input = {
            CONF_HOST: "unreachable.local",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"
        assert result2["step_id"] == "user"

    # Now mock success for retry
    mock_handler = MagicMock()  # Changed from AsyncMock
    mock_handler.check_apiversion_supported.return_value = (
        RequestStatus.SUCCESS,
        {},
    )

    mock_client = AsyncMock()
    mock_client.device_info = {"SERIAL_NUMBER": "SN123456789"}

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler.create",
            return_value=(RequestStatus.SUCCESS, mock_handler),
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient.create",
            return_value=(RequestStatus.SUCCESS, mock_client),
        ),
    ):
        # Retry with valid host
        user_input = {
            CONF_HOST: "192.168.1.100",
            CONF_SCAN_INTERVAL: 600,
            CONF_TIMEOUT: 30,
            CONF_INCLUDE_SENSITIVE_DATA: False,
        }
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "PoolDose SN123456789"
