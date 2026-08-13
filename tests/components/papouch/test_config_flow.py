"""Contains unittests for config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aiopapouch.exceptions import DeviceAuthError, DeviceLogicError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.papouch.config_flow import PapouchConfigFlow
from homeassistant.components.papouch.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    WEB_MODE_INDEX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry():
    """Fixture to mock the integration entry setup."""
    with patch(
        "homeassistant.components.papouch.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_discover_none():
    """Fixture to mock device discovery returning no devices."""
    with patch(
        "homeassistant.components.papouch.config_flow.async_discover_papouch_devices",
        return_value={},
    ) as mock:
        yield mock


@pytest.fixture
def mock_discover_found():
    """Fixture to mock device discovery returning a discovered device."""
    with patch(
        "homeassistant.components.papouch.config_flow.async_discover_papouch_devices",
        return_value={"192.168.1.50": ("Lab", "Quido")},
    ) as mock:
        yield mock


@pytest.fixture
def mock_api_client():
    """Fixture to mock API client fetch info, device mode and MAC methods."""
    with (
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.fetch_info"
        ) as mock_fetch,
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.get_device_mode",
            return_value=WEB_MODE_INDEX,
        ) as mock_mode,
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.get_device_info",
            return_value=("Quido", "Lab"),
        ) as mock_info,
        patch(
            "homeassistant.components.papouch.config_flow.PapouchHTTPClient.get_device_mac",
            return_value="00:11:22:33:44:55",
        ) as mock_mac,
    ):
        yield mock_fetch, mock_mode, mock_info, mock_mac


@pytest.fixture
def mock_create_device():
    """Fixture to mock device creation and return a mock device instance."""
    mock_device = MagicMock()
    mock_device.name = "Quido"
    mock_device.location = "Lab"
    mock_device.switch_to_web_mode = AsyncMock()

    with patch(
        "homeassistant.components.papouch.config_flow.create_device",
        return_value=mock_device,
    ) as mock_create:
        yield mock_create


@pytest.fixture
def dhcp_info():
    """Fixture providing sample DHCP service information for testing."""
    return DhcpServiceInfo(
        ip="192.168.1.100", macaddress="aabbccddeeff", hostname="papouch_device"
    )


async def test_manual_success(
    hass: HomeAssistant, mock_discover_none, mock_api_client, mock_setup_entry
) -> None:
    """Test successful manual setup of the integration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "admin"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.50"
    assert result2["data"]["ip_address"] == "192.168.1.50"
    assert result2["data"]["password"] == "admin"
    assert result2["data"]["device_name"] == "Quido (Lab)"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_success_fallback_title(
    hass: HomeAssistant, mock_discover_none, mock_api_client, mock_setup_entry
) -> None:
    """Test successful setup but fallback to Papouch Device if info fails."""
    _, _, mock_info, _ = mock_api_client
    mock_info.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Papouch Device - 192.168.1.50"


async def test_manual_connection_error(
    hass: HomeAssistant, mock_discover_none, mock_api_client
) -> None:
    """Test handling of connection errors during manual IP entry."""
    mock_fetch, _, _, _ = mock_api_client
    mock_fetch.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "supersecret"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_dhcp_discovery_success(
    hass: HomeAssistant, dhcp_info, mock_api_client, mock_create_device
) -> None:
    """Test DHCP discovery routes to confirmation form successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"]["name"] == "Quido (Lab) - 192.168.1.100"


async def test_dhcp_already_configured(hass: HomeAssistant, dhcp_info) -> None:
    """Test DHCP discovery aborts if the IP is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.100"},
        options={"refresh_rate": 60},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_ip_update(
    hass: HomeAssistant, dhcp_info, mock_setup_entry, mock_api_client
) -> None:
    """Test DHCP updates IP address of an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.99",
        data={"ip_address": "192.168.1.99"},
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["ip_address"] == "192.168.1.100"
    assert entry.title == "Quido (Lab) - 192.168.1.100"


async def test_dhcp_heal_legacy_entry(hass: HomeAssistant, dhcp_info) -> None:
    """Test DHCP updates an existing entry that lacks a unique_id."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.100",
        data={"ip_address": "192.168.1.100"},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff"


async def test_web_mode_mac_error(
    hass: HomeAssistant, mock_discover_none, mock_api_client, mock_create_device
) -> None:
    """Test web mode switch aborts if getting MAC address fails."""
    _, mock_mode, _, mock_mac = mock_api_client

    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "supersecret"},
    )

    mock_mac.side_effect = aiohttp.ClientError

    result_cannot_connect = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"next_step_id": "execute_switch"}
    )

    assert result_cannot_connect["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_cannot_connect["reason"] == "cannot_connect"


async def test_web_mode_switch(
    hass: HomeAssistant,
    mock_discover_none,
    mock_api_client,
    mock_create_device,
    mock_setup_entry,
) -> None:
    """Test the config flow when the device requires switching to WEB mode."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "supersecret"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.MENU
    assert result2["step_id"] == "web_mode"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"next_step_id": "execute_switch"}
    )

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["description"] == "web_mode_success"
    assert result3["title"] == "Quido (Lab) - 192.168.1.50"
    assert result3["data"]["password"] == "supersecret"
    mock_create_device.return_value.switch_to_web_mode.assert_called_once()


async def test_invalid_ip_format(hass: HomeAssistant, mock_discover_none) -> None:
    """Test handling of invalid IP address format during setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "999.invalid.ip", "refresh_rate": 60, "password": "supersecret"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"]["ip_address"] == "invalid_ip_format"


async def test_dhcp_unsupported_device(
    hass: HomeAssistant, dhcp_info, mock_api_client, mock_create_device
) -> None:
    """Test DHCP discovery aborts when an unsupported device is detected."""
    _, _, mock_info, _ = mock_api_client
    mock_info.return_value = ("UnknownDeviceName123", "Lab")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unsupported_device"


async def test_discovery_confirm_success(
    hass: HomeAssistant,
    dhcp_info,
    mock_api_client,
    mock_create_device,
    mock_setup_entry,
) -> None:
    """Test successful completion of the discovery confirmation step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"refresh_rate": 60, "password": "dhcp_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.100"
    assert result2["data"]["ip_address"] == "192.168.1.100"
    assert result2["data"]["password"] == "dhcp_password"


async def test_user_udp_discovery_and_manual_choice(
    hass: HomeAssistant, mock_discover_found
) -> None:
    """Test UDP discovery options and choosing manual IP entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "manual", "refresh_rate": 120, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "manual"


async def test_mode_missing_abort(
    hass: HomeAssistant, mock_discover_none, mock_api_client
) -> None:
    """Test config flow aborts when the device mode is missing."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = -1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "mode_is_missing"


async def test_web_mode_abort_switch(
    hass: HomeAssistant, mock_discover_none, mock_api_client
) -> None:
    """Test aborting the config flow from the web mode menu."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    result_cancel = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"next_step_id": "abort_switch"}
    )

    assert result_cancel["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_cancel["reason"] == "web_mode_required"


async def test_web_mode_unsupported_device(
    hass: HomeAssistant, mock_discover_none, mock_api_client, mock_create_device
) -> None:
    """Test config flow aborts when switching to web mode on an unsupported device."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    mock_create_device.return_value = None
    result_unsupported = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"next_step_id": "execute_switch"}
    )

    assert result_unsupported["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_unsupported["reason"] == "unsupported_device"


async def test_web_mode_client_error(
    hass: HomeAssistant, mock_discover_none, mock_api_client, mock_create_device
) -> None:
    """Test config flow aborts on client error during web mode switch execution."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    mock_create_device.side_effect = aiohttp.ClientError
    result_cannot_connect = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"next_step_id": "execute_switch"}
    )

    assert result_cannot_connect["type"] == data_entry_flow.FlowResultType.ABORT
    assert result_cannot_connect["reason"] == "cannot_connect"


async def test_dhcp_client_error(
    hass: HomeAssistant, dhcp_info, mock_api_client, mock_create_device
) -> None:
    """Test DHCP discovery aborts on client error when fetching device info."""
    _, _, mock_info, _ = mock_api_client
    mock_info.side_effect = aiohttp.ClientError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_discovery_confirm_mode_missing(
    hass: HomeAssistant, dhcp_info, mock_api_client, mock_create_device
) -> None:
    """Test discovery confirm aborts when mode is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = -1

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "mode_is_missing"


async def test_discovery_confirm_web_mode_redirect(
    hass: HomeAssistant, dhcp_info, mock_api_client, mock_create_device
) -> None:
    """Test discovery confirm redirects to web mode step if device is not in web mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "dhcp"}, data=dhcp_info
    )

    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.MENU
    assert result2["step_id"] == "web_mode"


async def test_user_no_discovery_routes_to_manual(
    hass: HomeAssistant, mock_discover_none
) -> None:
    """Test user step routes to manual when no devices are discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_fallback_defaults_from_saved_input(
    hass: HomeAssistant, mock_discover_found
) -> None:
    """Test that manual step loads default interval from saved input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "manual", "refresh_rate": 123},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "manual"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "ip_address": "999.invalid.ip",
            "refresh_rate": 123,
            "password": "password",
        },
    )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"]["ip_address"] == "invalid_ip_format"


async def test_user_with_discovered_ip_not_in_options(
    hass: HomeAssistant, mock_discover_found
) -> None:
    """Test user step handles edge case where discovered IP is not in options."""
    flow = PapouchConfigFlow()
    flow.hass = hass
    flow.discovered_ip = "10.0.0.99"

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_connection_success(
    hass: HomeAssistant, mock_discover_found, mock_api_client, mock_setup_entry
) -> None:
    """Test a successful connection directly from the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Quido (Lab) - 192.168.1.50"
    assert result2["data"]["ip_address"] == "192.168.1.50"
    assert result2["data"]["password"] == "password"


async def test_user_step_mode_missing(
    hass: HomeAssistant, mock_discover_found, mock_api_client
) -> None:
    """Test the mode_is_missing abort directly from the user step."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = -1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "mode_is_missing"


async def test_user_step_web_mode_redirect(
    hass: HomeAssistant, mock_discover_found, mock_api_client
) -> None:
    """Test redirect to web mode directly from the user step."""
    _, mock_mode, _, _ = mock_api_client
    mock_mode.return_value = 2

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.MENU
    assert result2["step_id"] == "web_mode"


async def test_udp_discovery_all_configured_routes_to_manual(
    hass: HomeAssistant, mock_discover_found
) -> None:
    """Test that if all discovered devices are already configured, it routes to manual."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.50"},
        options={"refresh_rate": 60},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_manual_already_configured(
    hass: HomeAssistant, mock_discover_none, mock_api_client
) -> None:
    """Test that manual IP entry aborts if the IP is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"ip_address": "192.168.1.50"},
        options={"refresh_rate": 60},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_manual_mac_error(
    hass: HomeAssistant, mock_discover_none, mock_api_client
) -> None:
    """Test manual flow aborts if getting MAC address fails."""
    _, _, _, mock_mac = mock_api_client

    mock_mac.side_effect = DeviceLogicError("No MAC found")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.50", "refresh_rate": 60, "password": "admin"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test the complete reauthentication flow (success and failures)."""
    mock_fetch, _, _, _ = mock_api_client

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.50",
        data={"ip_address": "192.168.1.50", "password": "old_password"},
    )
    entry.add_to_hass(hass)

    # 1. Start Reauth
    result = await entry.start_reauth_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # 2. Simulate bad password (DeviceAuthError)
    mock_fetch.side_effect = DeviceAuthError("Invalid password")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "wrong_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # 3. Simulate correct password (Success)
    mock_fetch.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "correct_password"},
    )

    assert result3["type"] == data_entry_flow.FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert entry.data["password"] == "correct_password"


async def test_reauth_connection_error(hass: HomeAssistant, mock_api_client) -> None:
    """Test reauth flow handles connection errors."""
    mock_fetch, _, _, _ = mock_api_client

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.50",
        data={"ip_address": "192.168.1.50", "password": "old_password"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    # Simulate network failure
    mock_fetch.side_effect = aiohttp.ClientError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test updating options via the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.100",
        data={"ip_address": "192.168.1.100", "password": ""},
        options={"refresh_rate": DEFAULT_SCAN_INTERVAL},
    )
    entry.add_to_hass(hass)

    with patch("homeassistant.components.papouch.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)

        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "refresh_rate": 30,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options == {"refresh_rate": 30}


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_api_client, mock_setup_entry
) -> None:
    """Test successful reconfiguration of the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.50",
        data={"ip_address": "192.168.1.50", "password": "old_password"},
        unique_id="00:11:22:33:44:55",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.60", "password": "new_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    assert entry.data["ip_address"] == "192.168.1.60"
    assert entry.data["password"] == "new_password"


async def test_reconfigure_connection_error(
    hass: HomeAssistant, mock_api_client
) -> None:
    """Test reconfiguration flow handles connection errors."""
    mock_fetch, _, _, _ = mock_api_client
    mock_fetch.side_effect = aiohttp.ClientError

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.50",
        data={"ip_address": "192.168.1.50", "password": "old_password"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.60", "password": "new_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_auth_error(hass: HomeAssistant, mock_api_client) -> None:
    """Test reconfiguration flow handles auth errors."""
    mock_fetch, _, _, _ = mock_api_client
    mock_fetch.side_effect = DeviceAuthError("Invalid password")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Quido (Lab) - 192.168.1.50",
        data={"ip_address": "192.168.1.50", "password": "old_password"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": entry.entry_id},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"ip_address": "192.168.1.60", "password": "wrong_password"},
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
