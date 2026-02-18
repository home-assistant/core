"""Test the Teltonika config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant import config_entries
from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_form_user_flow(
    hass: HomeAssistant, mock_teltasync: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUTX50 Test"
    assert result["data"] == {
        CONF_HOST: "https://192.168.1.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id == "1234567890"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (TeltonikaAuthenticationError("Invalid credentials"), "invalid_auth"),
        (TeltonikaConnectionError("Connection failed"), "cannot_connect"),
        (ValueError("Unexpected error"), "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unexpected_exception"],
)
async def test_form_error_with_recovery(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error_key: str,
) -> None:
    """Test we handle errors in config form and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt with error
    mock_teltasync_client.get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # Recover with working connection
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Test"
    device_info.device_identifier = "1234567890"
    mock_teltasync_client.get_device_info.side_effect = None
    mock_teltasync_client.get_device_info.return_value = device_info
    mock_teltasync_client.validate_credentials.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUTX50 Test"
    assert result["data"][CONF_HOST] == "https://192.168.1.1"
    assert result["result"].unique_id == "1234567890"


async def test_form_duplicate_entry(
    hass: HomeAssistant, mock_teltasync: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test duplicate config entry is handled."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("host_input", "expected_base_url", "expected_host"),
    [
        ("192.168.1.1", "https://192.168.1.1/api", "https://192.168.1.1"),
        ("http://192.168.1.1", "http://192.168.1.1/api", "http://192.168.1.1"),
        ("https://192.168.1.1", "https://192.168.1.1/api", "https://192.168.1.1"),
        ("https://192.168.1.1/api", "https://192.168.1.1/api", "https://192.168.1.1"),
        ("device.local", "https://device.local/api", "https://device.local"),
    ],
)
async def test_host_url_construction(
    hass: HomeAssistant,
    mock_teltasync: MagicMock,
    mock_teltasync_client: MagicMock,
    mock_setup_entry: AsyncMock,
    host_input: str,
    expected_base_url: str,
    expected_host: str,
) -> None:
    """Test that host URLs are constructed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: host_input,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    # Verify Teltasync was called with correct base URL
    assert mock_teltasync_client.get_device_info.call_count == 1
    call_args = mock_teltasync.call_args_list[0]
    assert call_args.kwargs["base_url"] == expected_base_url
    assert call_args.kwargs["verify_ssl"] is False

    # Verify the result is a created entry with normalized host
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data[CONF_HOST] == expected_host


async def test_form_user_flow_http_fallback(
    hass: HomeAssistant, mock_teltasync_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we fall back to HTTP when HTTPS fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First call (HTTPS) fails
    https_client = MagicMock()
    https_client.get_device_info.side_effect = TeltonikaConnectionError(
        "HTTPS unavailable"
    )
    https_client.close = AsyncMock()

    # Second call (HTTP) succeeds
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Test"
    device_info.device_identifier = "TESTFALLBACK"

    http_client = MagicMock()
    http_client.get_device_info = AsyncMock(return_value=device_info)
    http_client.validate_credentials = AsyncMock(return_value=True)
    http_client.close = AsyncMock()

    mock_teltasync_client.get_device_info.side_effect = [
        TeltonikaConnectionError("HTTPS unavailable"),
        mock_teltasync_client.get_device_info.return_value,
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "http://192.168.1.1"
    assert mock_teltasync_client.get_device_info.call_count == 2
    # HTTPS client should be closed before falling back
    assert mock_teltasync_client.close.call_count == 2


async def test_dhcp_discovery(
    hass: HomeAssistant, mock_teltasync_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test DHCP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    assert "name" in result["description_placeholders"]
    assert "host" in result["description_placeholders"]

    # Configure device info for the actual setup
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Discovered"
    device_info.device_identifier = "DISCOVERED123"
    mock_teltasync_client.get_device_info.return_value = device_info

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUTX50 Discovered"
    assert result["data"][CONF_HOST] == "https://192.168.1.50"
    assert result["data"][CONF_USERNAME] == "admin"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["result"].unique_id == "DISCOVERED123"


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant, mock_teltasync: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP discovery when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",  # Different IP
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Verify IP was updated
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.50"


async def test_dhcp_discovery_cannot_connect(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test DHCP discovery when device is not reachable."""
    # Simulate device not reachable via API
    mock_teltasync_client.get_device_info.side_effect = TeltonikaConnectionError(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    # Should abort if device is not reachable
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("exception", "error_key"),
    [
        (TeltonikaAuthenticationError("Invalid credentials"), "invalid_auth"),
        (TeltonikaConnectionError("Connection failed"), "cannot_connect"),
        (ValueError("Unexpected error"), "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unexpected_exception"],
)
async def test_dhcp_confirm_error_with_recovery(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error_key: str,
) -> None:
    """Test DHCP confirmation handles errors and can recover."""
    # Start the DHCP flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    # First attempt with error
    mock_teltasync_client.get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}
    assert result["step_id"] == "dhcp_confirm"

    # Recover with working connection
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Discovered"
    device_info.device_identifier = "DISCOVERED123"
    mock_teltasync_client.get_device_info.side_effect = None
    mock_teltasync_client.get_device_info.return_value = device_info
    mock_teltasync_client.validate_credentials.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUTX50 Discovered"
    assert result["data"][CONF_HOST] == "https://192.168.1.50"
    assert result["result"].unique_id == "DISCOVERED123"


async def test_validate_credentials_false(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test config flow when validate_credentials returns False."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    device_info = MagicMock()
    device_info.device_name = "Test Device"
    device_info.device_identifier = "TEST123"

    mock_teltasync_client.get_device_info.return_value = device_info
    mock_teltasync_client.validate_credentials.return_value = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
