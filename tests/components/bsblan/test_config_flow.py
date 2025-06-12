"""Tests for the BSBLan device config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock

from bsblan import BSBLANConnectionError
import pytest

from homeassistant.components.bsblan.const import CONF_PASSKEY, DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
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
def zeroconf_discovery_info_no_mac() -> Mock:
    """Return zeroconf discovery info for a BSBLAN device without MAC address."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {}  # No MAC in properties_raw either
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."
    return discovery_info


@pytest.fixture
def zeroconf_discovery_info_properties_raw() -> Mock:
    """Return zeroconf discovery info with MAC in properties_raw."""
    discovery_info = Mock()
    discovery_info.ip_address = ip_address("10.0.2.60")
    discovery_info.ip_addresses = [ip_address("10.0.2.60")]
    discovery_info.name = "BSB-LAN web service._http._tcp.local."
    discovery_info.type = "_http._tcp.local."
    discovery_info.properties = {}  # No MAC in properties
    discovery_info.properties_raw = {
        b"mac=00:80:41:19:69:90": b""
    }  # MAC in properties_raw
    discovery_info.port = 80
    discovery_info.hostname = "BSB-LAN.local."
    return discovery_info


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

    result2 = await _configure_flow(
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
        result2,
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

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result2,
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


async def test_zeroconf_discovery_mac_from_properties_raw(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info_properties_raw: Mock,
) -> None:
    """Test Zeroconf discovery when MAC is found in properties_raw instead of properties."""
    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_properties_raw)
    _assert_form_result(result, "discovery_confirm")

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result2,
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


async def test_zeroconf_discovery_no_mac_in_announcement(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info_no_mac: Mock,
) -> None:
    """Test Zeroconf discovery works when no MAC address is in the announcement."""
    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_no_mac)
    _assert_form_result(result, "discovery_confirm")

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    _assert_create_entry_result(
        result2,
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


async def test_zeroconf_discovery_connection_error(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    zeroconf_discovery_info: ZeroconfServiceInfo,
) -> None:
    """Test connection error during zeroconf discovery shows the correct form."""
    mock_bsblan.device.side_effect = BSBLANConnectionError

    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info)
    _assert_form_result(result, "discovery_confirm")

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result2, "discovery_confirm", {"base": "cannot_connect"})


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


async def test_zeroconf_discovery_mac_mismatch_updates_unique_id(
    hass: HomeAssistant,
    mock_bsblan: MagicMock,
    mock_setup_entry: AsyncMock,
    zeroconf_discovery_info_different_mac: ZeroconfServiceInfo,
) -> None:
    """Test Zeroconf discovery when MAC from discovery differs from device API."""
    # The fixture provides MAC "aa:bb:cc:dd:ee:ff" in Zeroconf discovery
    # But the mock device API returns "00:80:41:19:69:90" (from device.json)
    result = await _init_zeroconf_flow(hass, zeroconf_discovery_info_different_mac)
    _assert_form_result(result, "discovery_confirm")

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result2,
        format_mac("00:80:41:19:69:90"),  # Title should use MAC from device API
        {
            CONF_HOST: "10.0.2.60",
            CONF_PORT: 80,
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
        format_mac("00:80:41:19:69:90"),  # Unique ID updated to MAC from device API
    )

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_bsblan.device.mock_calls) == 1


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

    result2 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_form_result(result2, "discovery_confirm", {"base": "cannot_connect"})

    # Second attempt succeeds (connection is fixed)
    mock_bsblan.device.side_effect = None

    result3 = await _configure_flow(
        hass,
        result["flow_id"],
        {
            CONF_PASSKEY: "1234",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "admin1234",
        },
    )

    _assert_create_entry_result(
        result3,
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

    result2 = await _configure_flow(
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
        result2,
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
