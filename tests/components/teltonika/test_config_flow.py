"""Test the Teltonika config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from teltasync import TeltonikaAuthenticationError, TeltonikaConnectionError

from homeassistant import config_entries
from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


async def test_form_user_flow(
    hass: HomeAssistant, mock_teltasync: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form and can create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "RUTX50 Test"
    assert result2["data"] == {
        CONF_HOST: "https://192.168.1.1",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "password",
        "validate_ssl": False,
    }


async def test_form_invalid_auth_with_recovery(
    hass: HomeAssistant, mock_teltasync_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt with wrong password
    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=TeltonikaAuthenticationError("Invalid credentials")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong_password",
            "validate_ssl": False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # Recover with correct credentials
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Test"
    device_info.device_identifier = "TEST1234567890"
    mock_teltasync_client.get_device_info = AsyncMock(return_value=device_info)
    mock_teltasync_client.validate_credentials = AsyncMock(return_value=True)

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "correct_password",
            "validate_ssl": False,
        },
    )

    await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "RUTX50 Test"
    assert result3["data"][CONF_HOST] == "https://192.168.1.1"


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=TeltonikaConnectionError("Connection failed")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_duplicate_entry(
    hass: HomeAssistant, mock_teltasync: MagicMock
) -> None:
    """Test duplicate config entry is handled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
        unique_id="TEST1234567890",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_unexpected_exception(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test we handle unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=ValueError("Unexpected error")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


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
    mock_setup_entry: AsyncMock,
    host_input: str,
    expected_base_url: str,
    expected_host: str,
) -> None:
    """Test that host URLs are constructed correctly."""
    # Set unique device ID for each host
    device_info = MagicMock()
    device_info.device_name = "RUTX50 Test"
    device_info.device_identifier = f"TEST{hash(host_input)}"
    mock_teltasync.return_value.get_device_info = AsyncMock(return_value=device_info)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: host_input,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    await hass.async_block_till_done()

    # Verify Teltasync was called with correct base URL
    assert mock_teltasync.call_count == 1
    call_args = mock_teltasync.call_args_list[0]
    assert call_args.kwargs["base_url"] == expected_base_url
    assert call_args.kwargs["verify_ssl"] is False

    # Verify stored host matches expected normalization
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == expected_host


async def test_form_user_flow_http_fallback(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we fall back to HTTP when HTTPS fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.teltonika.config_flow.Teltasync",
        autospec=True,
    ) as mock_teltasync:
        # First call (HTTPS) fails
        https_client = MagicMock()
        https_client.get_device_info = AsyncMock(
            side_effect=TeltonikaConnectionError("HTTPS unavailable")
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

        mock_teltasync.side_effect = [https_client, http_client]

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.1",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                "validate_ssl": False,
            },
        )

        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_HOST] == "http://192.168.1.1"
        assert mock_teltasync.call_count == 2
        # HTTPS client should be closed before falling back
        https_client.close.assert_awaited_once()
        http_client.close.assert_awaited_once()


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
    mock_teltasync_client.get_device_info = AsyncMock(return_value=device_info)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "RUTX50 Discovered"
    assert result2["data"][CONF_HOST] == "https://192.168.1.50"
    assert result2["data"][CONF_USERNAME] == "admin"
    assert result2["data"][CONF_PASSWORD] == "password"


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant, mock_teltasync: MagicMock
) -> None:
    """Test DHCP discovery when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "https://192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
        unique_id="TEST1234567890",
    )
    entry.add_to_hass(hass)

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
    assert entry.data[CONF_HOST] == "192.168.1.50"


async def test_dhcp_discovery_auth_required(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test DHCP discovery when device info fetch fails."""
    # Simulate device not reachable via API
    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=TeltonikaConnectionError("Connection failed")
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


async def test_dhcp_confirm_invalid_auth(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test DHCP confirmation with invalid credentials."""
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

    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=TeltonikaAuthenticationError("Invalid credentials")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong_password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    assert result2["step_id"] == "dhcp_confirm"


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

    mock_teltasync_client.get_device_info = AsyncMock(return_value=device_info)
    mock_teltasync_client.validate_credentials = AsyncMock(return_value=False)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            "validate_ssl": False,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_dhcp_confirm_unexpected_exception(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test unexpected exception during DHCP confirmation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=ValueError("Unexpected error")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
    assert result2["step_id"] == "dhcp_confirm"


async def test_dhcp_confirm_cannot_connect(
    hass: HomeAssistant, mock_teltasync_client: MagicMock
) -> None:
    """Test DHCP confirmation with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.168.1.50",
            macaddress="209727112233",
            hostname="teltonika",
        ),
    )

    mock_teltasync_client.get_device_info = AsyncMock(
        side_effect=TeltonikaConnectionError("Connection failed")
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
    assert result2["step_id"] == "dhcp_confirm"
