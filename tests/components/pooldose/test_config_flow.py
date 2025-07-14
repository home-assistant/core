"""Test the Seko Pooldose config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from pooldose.request_handler import RequestStatus
import pytest

from homeassistant.components.pooldose.const import CONF_SERIALNUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_request_handler():
    """Create a mock RequestHandler."""
    handler = MagicMock()
    handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    handler.is_connected = True
    return handler


@pytest.fixture
def mock_pooldose_client():
    """Create a mock PooldoseClient."""
    client = MagicMock()
    client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    client.is_connected = True
    return client


async def test_form_shows_and_creates_entry(
    hass: HomeAssistant, mock_request_handler, mock_pooldose_client
) -> None:
    """Test that the form is shown and entry is created on valid input."""
    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_request_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_pooldose_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "PoolDose SN123456789"
        assert result2["data"] == {
            CONF_HOST: "192.168.1.100",
            CONF_SERIALNUMBER: "SN123456789",
        }


async def test_form_cannot_connect_host_unreachable(hass: HomeAssistant) -> None:
    """Test that the form shows an error if the device is unreachable."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
    mock_handler.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler",
        return_value=mock_handler,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"
        assert result2["step_id"] == "user"


async def test_form_params_fetch_failed(hass: HomeAssistant) -> None:
    """Test that the form shows error when parameters cannot be fetched."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.PARAMS_FETCH_FAILED)
    mock_handler.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler",
        return_value=mock_handler,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "params_fetch_failed"  # Fixed typo
        assert result2["step_id"] == "user"


async def test_form_api_version_not_set(hass: HomeAssistant) -> None:
    """Test that the form shows error when API version is not set."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.NO_DATA, {})
    )
    mock_handler.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler",
        return_value=mock_handler,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "api_not_set"
        assert result2["step_id"] == "user"


async def test_form_api_version_unsupported(hass: HomeAssistant) -> None:
    """Test that the form shows error when API version is unsupported."""
    mock_handler = MagicMock()
    api_versions = {"api_version_is": "v0.9", "api_version_should": "v1.0"}
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.API_VERSION_UNSUPPORTED, api_versions)
    )
    mock_handler.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler",
        return_value=mock_handler,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "api_not_supported"
        assert result2["description_placeholders"] == api_versions
        assert result2["step_id"] == "user"


async def test_form_client_creation_failed(hass: HomeAssistant) -> None:
    """Test that the form shows error when client creation fails."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=RequestStatus.UNKNOWN_ERROR)
    mock_client.is_connected = False

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"
        assert result2["step_id"] == "user"


async def test_duplicate_entry_aborts(hass: HomeAssistant) -> None:
    """Test that the flow aborts if the device is already configured."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="SN123456789",
        data={CONF_HOST: "192.168.1.50", CONF_SERIALNUMBER: "SN123456789"},
    )
    existing_entry.add_to_hass(hass)

    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_form_handles_missing_serial_number(hass: HomeAssistant) -> None:
    """Test handling when device_info doesn't contain serial number."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {}  # No SERIAL_NUMBER
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        # Should show error because serial number is required
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "no_serial_number"
        assert result2["step_id"] == "user"


async def test_form_no_device_info(hass: HomeAssistant) -> None:
    """Test that the form shows error when device_info is None."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = None
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "no_device_info"
        assert result2["step_id"] == "user"


async def test_form_no_serial_number_found(hass: HomeAssistant) -> None:
    """Test that the form shows error when no serial number is found."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"OTHER_FIELD": "value"}  # No SERIAL_NUMBER
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "no_serial_number"
        assert result2["step_id"] == "user"


async def test_form_empty_serial_number(hass: HomeAssistant) -> None:
    """Test that the form shows error when serial number is empty."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"SERIAL_NUMBER": ""}  # Empty string
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "192.168.1.100"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "no_serial_number"
        assert result2["step_id"] == "user"


async def test_form_retry_after_error(hass: HomeAssistant) -> None:
    """Test that user can retry after connection error."""
    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    # First attempt fails
    mock_handler_fail = MagicMock()
    mock_handler_fail.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
    mock_handler_fail.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.RequestHandler",
        return_value=mock_handler_fail,
    ):
        user_input = {CONF_HOST: "unreachable.local"}
        result2 = await hass.config_entries.flow.async_configure(flow_id, user_input)

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"
        assert result2["step_id"] == "user"

    # Second attempt succeeds
    mock_handler_success = MagicMock()
    mock_handler_success.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler_success.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler_success.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler_success,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        user_input = {CONF_HOST: "192.168.1.100"}
        result3 = await hass.config_entries.flow.async_configure(flow_id, user_input)

        assert result3["type"] == FlowResultType.CREATE_ENTRY
        assert result3["title"] == "PoolDose SN123456789"


async def test_form_with_hostname(hass: HomeAssistant) -> None:
    """Test form submission with hostname."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "pooldose.local"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_HOST: "pooldose.local",
            CONF_SERIALNUMBER: "SN123456789",
        }


async def test_form_with_default_host(hass: HomeAssistant) -> None:
    """Test form submission with default host."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    mock_client = MagicMock()
    mock_client.device_info = {"SERIAL_NUMBER": "SN123456789"}
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.is_connected = True

    with (
        patch(
            "homeassistant.components.pooldose.config_flow.RequestHandler",
            return_value=mock_handler,
        ),
        patch(
            "homeassistant.components.pooldose.config_flow.PooldoseClient",
            return_value=mock_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        user_input = {CONF_HOST: "KOMMSPOT"}
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            CONF_HOST: "KOMMSPOT",
            CONF_SERIALNUMBER: "SN123456789",
        }


async def test_form_with_different_client_error_statuses(hass: HomeAssistant) -> None:
    """Test form handles different error statuses from client."""
    mock_handler = MagicMock()
    mock_handler.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_handler.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_handler.is_connected = True

    # Test with different client error statuses
    error_statuses = [
        RequestStatus.HOST_UNREACHABLE,
        RequestStatus.PARAMS_FETCH_FAILED,
        RequestStatus.UNKNOWN_ERROR,
    ]

    for status in error_statuses:
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=status)
        mock_client.is_connected = False

        with (
            patch(
                "homeassistant.components.pooldose.config_flow.RequestHandler",
                return_value=mock_handler,
            ),
            patch(
                "homeassistant.components.pooldose.config_flow.PooldoseClient",
                return_value=mock_client,
            ),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}
            )

            user_input = {CONF_HOST: "192.168.1.100"}
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )

            assert result2["type"] == FlowResultType.FORM
            assert result2["errors"]["base"] == "cannot_connect"
            assert result2["step_id"] == "user"
