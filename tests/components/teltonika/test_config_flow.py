"""Test the Teltonika config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError
from teltasync.unauthorized import UnauthorizedStatusData

from homeassistant import config_entries
from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_user_flow(hass: HomeAssistant, mock_teltasync: MagicMock) -> None:
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
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_error_with_recovery(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
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
@pytest.mark.usefixtures("mock_setup_entry")
async def test_host_url_construction(
    hass: HomeAssistant,
    mock_teltasync: MagicMock,
    mock_teltasync_client: MagicMock,
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_user_flow_http_fallback(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
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
@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_confirm_error_with_recovery(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "admin"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.1"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_success_rut240(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """Reauth on a RUT240 falls back to mnf_info.serial for unique_id matching."""
    mock_teltasync_client.get_device_info.return_value = rut240_device_info
    mock_teltasync_client.validate_credentials.return_value = True
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TeltonikaAuthenticationError("Invalid credentials"), "invalid_auth"),
        (TeltonikaConnectionError("Connection failed"), "cannot_connect"),
        (ValueError("Unexpected error"), "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unexpected_exception"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors_with_recovery(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth flow error handling with successful recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_teltasync_client.get_device_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "bad_password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert result["step_id"] == "reauth_confirm"

    mock_teltasync_client.get_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "new_password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "admin"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.1"


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow aborts when device serial doesn't match."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    device_info = MagicMock()
    device_info.device_name = "RUTX50 Different"
    device_info.device_identifier = "DIFFERENT1234567890"
    mock_teltasync_client.get_device_info = AsyncMock(return_value=device_info)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_user_flow_rut240(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """RUT240 firmware omits device_identifier; falls back to serial."""
    mock_teltasync_client.get_device_info.return_value = rut240_device_info
    mock_teltasync_client.validate_credentials.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUT240"
    assert result["result"].unique_id == "1234567890"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_rut240(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """RUT240 DHCP discovery proceeds to confirmation when the MAC isn't yet known."""
    mock_teltasync_client.get_device_info.return_value = rut240_device_info
    mock_teltasync_client.validate_credentials.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727aabbcc",
            hostname="teltonika",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"
    assert "name" in result["description_placeholders"]
    assert "host" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RUT240"
    assert result["data"][CONF_HOST] == "https://192.168.1.50"
    assert result["data"][CONF_USERNAME] == "admin"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["result"].unique_id == "1234567890"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_dhcp_discovery_rut240_repeated_advertisement(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """A second DHCP advertisement before dhcp_confirm finishes is suppressed."""
    mock_teltasync_client.get_device_info.return_value = rut240_device_info

    discovery = DhcpServiceInfo(
        ip="192.168.1.50",
        macaddress="209727aabbcc",
        hostname="teltonika",
    )

    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=discovery
    )
    assert first["type"] is FlowResultType.FORM
    assert first["step_id"] == "dhcp_confirm"

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=discovery
    )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"


async def test_dhcp_discovery_rut240_already_configured_updates_host(
    hass: HomeAssistant,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """An already-configured RUT240 gets its host updated through dhcp_confirm."""
    mock_config_entry.add_to_hass(hass)
    mock_teltasync_client.get_device_info.return_value = rut240_device_info
    mock_teltasync_client.validate_credentials.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.99.99",
            macaddress="209727aabbcc",
            hostname="teltonika",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "https://192.168.99.99"


async def test_dhcp_discovery_apiv1_already_configured_aborts(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_teltasync_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    rut240_device_info: UnauthorizedStatusData,
) -> None:
    """API v1.0 RUT240 known by MAC aborts before dhcp_confirm."""
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, mock_config_entry.unique_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, "20:97:27:aa:bb:cc")},
    )
    mock_teltasync_client.get_device_info.return_value = rut240_device_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.99.99",
            macaddress="209727aabbcc",
            hostname="teltonika",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.99.99"
    mock_teltasync_client.validate_credentials.assert_not_called()
