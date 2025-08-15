"""Tests for the BSBLan device config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from bsblan import BSBLANAuthError, BSBLANConnectionError, BSBLANError
import pytest

from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

# ZeroconfServiceInfo fixtures for different discovery scenarios


@pytest.fixture
def zeroconf_discovery_info() -> ZeroconfServiceInfo:
    """Return zeroconf discovery info for a BSBLAN device with MAC address."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "00:80:41:19:69:90"},
        port=80,
        hostname="BSB-LAN.local.",
    )


@pytest.fixture
def zeroconf_discovery_info_no_mac() -> ZeroconfServiceInfo:
    """Return zeroconf discovery info for a BSBLAN device without MAC address."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={},  # No MAC in properties
        port=80,
        hostname="BSB-LAN.local.",
    )


@pytest.fixture
def zeroconf_discovery_info_different_mac() -> ZeroconfServiceInfo:
    """Return zeroconf discovery info with a different MAC than the device API returns."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("10.0.2.60"),
        ip_addresses=[ip_address("10.0.2.60")],
        name="BSB-LAN web service._http._tcp.local.",
        type="_http._tcp.local.",
        properties={"mac": "aa:bb:cc:dd:ee:ff"},  # Different MAC than in device.json
        port=80,
        hostname="BSB-LAN.local.",
    )


# Helper functions to reduce repetition


async def _init_user_flow(hass: HomeAssistant, user_input: dict | None = None):
    """Initialize a user config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )


async def _init_zeroconf_flow(hass: HomeAssistant, discovery_info):
    """Initialize a zeroconf config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )


async def _configure_flow(hass: HomeAssistant, flow_id: str, user_input: dict):
    """Configure a flow with user input."""
    return await hass.config_entries.flow.async_configure(
        flow_id,
        user_input=user_input,
    )


def _assert_create_entry_result(
    result, expected_title: str, expected_data: dict, expected_unique_id: str
):
    """Assert that result is a successful CREATE_ENTRY."""
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == expected_title
    assert result.get("data") == expected_data
    assert "result" in result
    assert result["result"].unique_id == expected_unique_id


def _assert_form_result(
    result, expected_step_id: str, expected_errors: dict | None = None
):
    """Assert that result is a FORM with correct step and optional errors."""
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == expected_step_id
    if expected_errors is None:
        # Handle both None and {} as valid "no errors" states (like other integrations)
        assert result.get("errors") in ({}, None)
    else:
        assert result.get("errors") == expected_errors


def _assert_abort_result(result, expected_reason: str):
    """Assert that result is an ABORT with correct reason."""
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await _init_user_flow(hass)
    _assert_form_result(result, "user")

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result,
        format_mac("00:80:41:19:69:90"),
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        format_mac("00:80:41:19:69:90"),
    )

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await _init_user_flow(hass)
    _assert_form_result(result, "user")


async def test_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan connection error."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result, "user", {"base": "cannot_connect"})


async def test_authentication_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test we show user form on BSBLan authentication error with field preservation."""
    mock_bsblan.device.side_effect = BSBLANAuthError

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8080,
        CONF_PASSKEY: "secret",
        CONF_USERNAME: "testuser",
        CONF_PASSWORD: "wrongpassword",
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_auth"}
    assert result.get("step_id") == "user"

    # Verify that user input is preserved in the form
    data_schema = result.get("data_schema")
    assert data_schema is not None

    # Check that the form fields contain the previously entered values
    host_field = next(
        field for field in data_schema.schema if field.schema == CONF_HOST
    )
    port_field = next(
        field for field in data_schema.schema if field.schema == CONF_PORT
    )
    passkey_field = next(
        field for field in data_schema.schema if field.schema == CONF_PASSKEY
    )
    username_field = next(
        field for field in data_schema.schema if field.schema == CONF_USERNAME
    )
    password_field = next(
        field for field in data_schema.schema if field.schema == CONF_PASSWORD
    )

    # The defaults are callable functions, so we need to call them
    assert host_field.default() == "192.168.1.100"
    assert port_field.default() == 8080
    assert passkey_field.default() == "secret"
    assert username_field.default() == "testuser"
    assert password_field.default() == "wrongpassword"


async def test_authentication_error_vs_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test that authentication and connection errors are handled differently."""
    # Test connection error first
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
        },
    )

    _assert_form_result(result, "user", {"base": "cannot_connect"})

    # Reset and test authentication error
    mock_bsblan.device.side_effect = BSBLANAuthError

    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrongpass",
        },
    )

    _assert_form_result(result, "user", {"base": "invalid_auth"})


async def test_user_device_exists_abort(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort flow if BSBLAN device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_abort_result(result, "already_configured")


async def test_zeroconf_discovery(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test the Zeroconf discovery flow."""
    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_form_result(result, "discovery_confirm")

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result,
        format_mac("00:80:41:19:69:90"),
        {
            CONF_HOST: "10.0.2.60",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        format_mac("00:80:41:19:69:90"),
    )

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_abort_if_existing_entry_for_zeroconf(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test we abort if the same host/port already exists during zeroconf discovery."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_abort_result(result, "already_configured")


async def test_zeroconf_discovery_no_mac_requires_auth(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info_no_mac: ZeroconfServiceInfo,
) -> None:
    """Test Zeroconf discovery when no MAC in announcement and device requires auth."""
    # Make the first API call (without auth) fail, second call (with auth) succeed
    mock_bsblan.device.side_effect = [
        BSBLANConnectionError,
        mock_bsblan.device.return_value,
    ]

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_no_mac)
    _assert_form_result(result, "discovery_confirm")

    # Reset side_effect for the second call to succeed
    mock_bsblan.device.side_effect = None

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    _assert_create_entry_result(
        result,
        "00:80:41:19:69:90",  # MAC from fixture file
        {
            CONF_HOST: "10.0.2.60",
            CONF_PORT: 80,
            CONF_PASSKEY: None,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
        "00:80:41:19:69:90",
    )

    # Should be called 3 times: once without auth (fails), twice with auth (in _validate_and_create)
    assert len(mock_bsblan.device.mock_calls) == 3


async def test_zeroconf_discovery_no_mac_no_auth_required(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info_no_mac: ZeroconfServiceInfo,
) -> None:
    """Test Zeroconf discovery when no MAC in announcement but device accessible without auth."""
    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_no_mac)

    # Should now show the discovery_confirm form to the user
    _assert_form_result(result, "discovery_confirm")

    # User confirms the discovery
    result = await _configure_flow(hass, result["flow_id"], {})

    _assert_create_entry_result(
        result,
        "00:80:41:19:69:90",  # MAC from fixture file
        {
            CONF_HOST: "10.0.2.60",
            CONF_PORT: 80,
            CONF_PASSKEY: None,
            CONF_USERNAME: None,
            CONF_PASSWORD: None,
        },
        "00:80:41:19:69:90",
    )

    assert len(mock_setup_entry.mock_calls) == 1
    # Should be called once in zeroconf step, as _validate_and_create is skipped
    assert len(mock_bsblan.device.mock_calls) == 1


async def test_zeroconf_discovery_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test connection error during zeroconf discovery shows the correct form."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_form_result(result, "discovery_confirm")

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result, "discovery_confirm", {"base": "cannot_connect"})


async def test_zeroconf_discovery_updates_host_port_on_existing_entry(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test that discovered devices update host/port of existing entries."""
    # Create an existing entry with different host/port
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",  # Different IP
            CONF_PORT: 8080,  # Different port
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_abort_result(result, "already_configured")

    # Verify the existing entry WAS updated with new host/port from discovery
    assert entry.data[CONF_HOST] == "10.0.2.60"  # Updated host from discovery
    assert entry.data[CONF_PORT] == 80  # Updated port from discovery


async def test_user_flow_can_update_existing_host_port(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test that manual user configuration can update host/port of existing entries."""
    # Create an existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 8080,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Try to configure the same device with different host/port via user flow
    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "10.0.2.60",  # Different IP
            CONF_PORT: 80,  # Different port
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_abort_result(result, "already_configured")

    # Verify the existing entry WAS updated with new host/port (user flow behavior)
    assert entry.data[CONF_HOST] == "10.0.2.60"  # Updated host
    assert entry.data[CONF_PORT] == 80  # Updated port


async def test_zeroconf_discovery_connection_error_recovery(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test connection error during zeroconf discovery can be recovered from."""
    # First attempt fails with connection error
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_form_result(result, "discovery_confirm")

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result, "discovery_confirm", {"base": "cannot_connect"})

    # Second attempt succeeds (connection is fixed)
    mock_bsblan.device.side_effect = None

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result,
        format_mac("00:80:41:19:69:90"),
        {
            CONF_HOST: "10.0.2.60",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        format_mac("00:80:41:19:69:90"),
    )

    assert len(mock_setup_entry.mock_calls) == 1
    # Should have been called twice: first failed, second succeeded
    assert len(mock_bsblan.device.mock_calls) == 2


async def test_connection_error_recovery(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we can recover from BSBLan connection error in user flow."""
    # First attempt fails with connection error
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_user_flow(
        hass,
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result, "user", {"base": "cannot_connect"})

    # Second attempt succeeds (connection is fixed)
    mock_bsblan.device.side_effect = None

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result,
        format_mac("00:80:41:19:69:90"),
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        format_mac("00:80:41:19:69:90"),
    )

    assert len(mock_setup_entry.mock_calls) == 1
    # Should have been called twice: first failed, second succeeded
    assert len(mock_bsblan.device.mock_calls) == 2


async def test_zeroconf_discovery_no_mac_duplicate_host_port(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info_no_mac: ZeroconfServiceInfo,
) -> None:
    """Test Zeroconf discovery aborts when no MAC and same host/port already configured."""
    # Create an existing entry with same host/port but no unique_id
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.2.60",  # Same IP as discovery
            CONF_PORT: 80,  # Same port as discovery
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        unique_id=None,  # Old entry without unique_id
    )
    entry.add_to_hass(hass)

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_no_mac)
    _assert_abort_result(result, "already_configured")

    # Should not call device API since we abort early
    assert len(mock_bsblan.device.mock_calls) == 0


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    _assert_form_result(result, "reauth_confirm")

    # Check that the form has the correct description placeholder
    assert result.get("description_placeholders") == {"name": "BSBLAN Setup"}

    # Check that existing values are preserved as defaults
    data_schema = result.get("data_schema")
    assert data_schema is not None

    # Complete reauth with new credentials
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "new_passkey",
            CONF_USERNAME: "new_admin",
            CONF_PASSWORD: "new_password",
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify config entry was updated with new credentials
    assert mock_config_entry.data[CONF_PASSKEY] == "new_passkey"
    assert mock_config_entry.data[CONF_USERNAME] == "new_admin"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
    # Verify host and port remain unchanged
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"
    assert mock_config_entry.data[CONF_PORT] == 80


async def test_reauth_flow_auth_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with authentication error."""
    mock_config_entry.add_to_hass(hass)

    # Mock authentication error
    mock_bsblan.device.side_effect = BSBLANAuthError

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    _assert_form_result(result, "reauth_confirm")

    # Submit with wrong credentials
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "wrong_passkey",
            CONF_USERNAME: "wrong_admin",
            CONF_PASSWORD: "wrong_password",
        },
    )

    _assert_form_result(result, "reauth_confirm", {"base": "invalid_auth"})

    # Verify that user input is preserved in the form after error
    data_schema = result.get("data_schema")
    assert data_schema is not None

    # Check that the form fields contain the previously entered values
    passkey_field = next(
        field for field in data_schema.schema if field.schema == CONF_PASSKEY
    )
    username_field = next(
        field for field in data_schema.schema if field.schema == CONF_USERNAME
    )

    assert passkey_field.default() == "wrong_passkey"
    assert username_field.default() == "wrong_admin"


async def test_reauth_flow_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with connection error."""
    mock_config_entry.add_to_hass(hass)

    # Mock connection error
    mock_bsblan.device.side_effect = BSBLANConnectionError

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    _assert_form_result(result, "reauth_confirm")

    # Submit credentials but get connection error
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result, "reauth_confirm", {"base": "cannot_connect"})


async def test_reauth_flow_preserves_existing_values(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reauth flow preserves existing values when user doesn't change them."""
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    _assert_form_result(result, "reauth_confirm")

    # Submit without changing any credentials (only password is provided)
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSWORD: "new_password_only",
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify that existing passkey and username are preserved
    assert mock_config_entry.data[CONF_PASSKEY] == "1234"  # Original value
    assert mock_config_entry.data[CONF_USERNAME] == "admin"  # Original value
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password_only"  # New value


async def test_reauth_flow_partial_credentials_update(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with partial credential updates."""
    mock_config_entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    # Submit with only username and password changes
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_USERNAME: "new_admin",
            CONF_PASSWORD: "new_password",
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify partial update: passkey preserved, username and password updated
    assert mock_config_entry.data[CONF_PASSKEY] == "1234"  # Original preserved
    assert mock_config_entry.data[CONF_USERNAME] == "new_admin"  # Updated
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"  # Updated
    # Host and port should remain unchanged
    assert mock_config_entry.data[CONF_HOST] == "127.0.0.1"
    assert mock_config_entry.data[CONF_PORT] == 80


async def test_reauth_flow_preserves_non_credential_fields(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test reauth flow preserves non-credential fields using data_updates."""
    # Create a config entry with additional custom fields that should be preserved
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "old_key",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
            # Add some custom fields that should be preserved
            "custom_field": "should_be_preserved",
            "another_field": 42,
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    # Submit with only new credentials
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "new_key",
            CONF_USERNAME: "new_user",
            CONF_PASSWORD: "new_pass",
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify that only the provided fields were updated, others preserved
    assert entry.data[CONF_PASSKEY] == "new_key"  # Updated
    assert entry.data[CONF_USERNAME] == "new_user"  # Updated
    assert entry.data[CONF_PASSWORD] == "new_pass"  # Updated

    # These fields should remain unchanged (preserved by data_updates)
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_PORT] == 80
    assert entry.data["custom_field"] == "should_be_preserved"
    assert entry.data["another_field"] == 42


async def test_reauth_flow_clears_credentials_with_empty_strings(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test reauth flow can clear credentials by providing empty strings."""
    # Create a config entry with existing credentials
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "existing_key",
            CONF_USERNAME: "existing_user",
            CONF_PASSWORD: "existing_pass",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    # Submit with empty strings to clear credentials
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "",  # Clear passkey
            CONF_USERNAME: "",  # Clear username
            CONF_PASSWORD: "",  # Clear password
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify that credentials were cleared (set to empty strings)
    assert entry.data[CONF_PASSKEY] == ""
    assert entry.data[CONF_USERNAME] == ""
    assert entry.data[CONF_PASSWORD] == ""

    # Host and port should remain unchanged
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_PORT] == 80


async def test_reauth_flow_partial_clear_credentials(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
) -> None:
    """Test reauth flow can partially clear some credentials while updating others."""
    # Create a config entry with existing credentials
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_PASSKEY: "existing_key",
            CONF_USERNAME: "existing_user",
            CONF_PASSWORD: "existing_pass",
        },
        unique_id="00:80:41:19:69:90",
    )
    entry.add_to_hass(hass)

    # Start reauth flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
    )

    # Submit with mix of clearing and updating credentials
    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "",  # Clear passkey
            CONF_USERNAME: "new_user",  # Update username
            CONF_PASSWORD: "",  # Clear password
        },
    )

    _assert_abort_result(result, "reauth_successful")

    # Verify mixed update: some cleared, some updated, some preserved
    assert entry.data[CONF_PASSKEY] == ""  # Cleared
    assert entry.data[CONF_USERNAME] == "new_user"  # Updated
    assert entry.data[CONF_PASSWORD] == ""  # Cleared

    # Host and port should remain unchanged
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_PORT] == 80


async def test_zeroconf_discovery_auth_error_during_confirm(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test authentication error during discovery_confirm step."""
    # Remove MAC from discovery to force discovery_confirm step
    zeroconf_discovery_info.properties.pop("mac", None)

    # Setup device to require authentication during initial discovery
    mock_bsblan.device.side_effect = BSBLANError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_discovery_info,
    )

    _assert_form_result(result, "discovery_confirm")

    # Now setup auth error for the confirmation step
    mock_bsblan.device.side_effect = BSBLANAuthError

    result = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "wrong_key",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong_password",
        },
    )

    # Should show the discovery_confirm form again with auth error
    _assert_form_result(result, "discovery_confirm", {"base": "invalid_auth"})
