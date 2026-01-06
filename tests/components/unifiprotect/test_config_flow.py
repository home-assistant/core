"""Test the UniFi Protect config flow."""

from __future__ import annotations

from dataclasses import asdict
import socket
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect import NotAuthorized, NvrError, ProtectApiClient
from uiprotect.data import NVR, Bootstrap, CloudAccount, Version
from uiprotect.exceptions import ClientError

from homeassistant import config_entries
from homeassistant.components.unifiprotect.const import (
    CONF_ALL_UPDATES,
    CONF_DISABLE_RTSP,
    CONF_OVERRIDE_CHOST,
    DOMAIN,
)
from homeassistant.components.unifiprotect.utils import _async_unifi_mac_from_hass
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from . import (
    DEVICE_HOSTNAME,
    DEVICE_IP_ADDRESS,
    DEVICE_MAC_ADDRESS,
    DIRECT_CONNECT_DOMAIN,
    UNIFI_DISCOVERY,
    UNIFI_DISCOVERY_PARTIAL,
    _patch_discovery,
)
from .conftest import (
    DEFAULT_API_KEY,
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    MAC_ADDR,
)

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    hostname=DEVICE_HOSTNAME,
    ip=DEVICE_IP_ADDRESS,
    macaddress=DEVICE_MAC_ADDRESS.lower().replace(":", ""),
)
SSDP_DISCOVERY = (
    SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location=f"http://{DEVICE_IP_ADDRESS}:41417/rootDesc.xml",
        upnp={
            "friendlyName": "UniFi Dream Machine",
            "modelDescription": "UniFi Dream Machine Pro",
            "serialNumber": DEVICE_MAC_ADDRESS,
        },
    ),
)

# Base user input without credentials (for tests that override them)
BASE_USER_INPUT = {
    CONF_HOST: DEFAULT_HOST,
    CONF_PORT: DEFAULT_PORT,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    CONF_USERNAME: DEFAULT_USERNAME,
}

# Common user input for reconfigure flow tests
RECONFIGURE_USER_INPUT = {
    **BASE_USER_INPUT,
    CONF_PASSWORD: DEFAULT_PASSWORD,
    CONF_API_KEY: DEFAULT_API_KEY,
}

UNIFI_DISCOVERY_DICT = asdict(UNIFI_DISCOVERY)
UNIFI_DISCOVERY_DICT_PARTIAL = asdict(UNIFI_DISCOVERY_PARTIAL)


async def _complete_reconfigure_flow(
    hass: HomeAssistant,
    flow_id: str,
    nvr: NVR,
    bootstrap: Bootstrap,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> ConfigFlowResult:
    """Complete a reconfigure flow to terminal state after an error.

    Sets up mocks for successful completion and returns the result.
    Caller should assert the expected terminal state.
    """
    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    mock_api_bootstrap.side_effect = None
    mock_api_bootstrap.return_value = bootstrap
    mock_api_meta_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        RECONFIGURE_USER_INPUT,
    )
    await hass.async_block_till_done()
    return result


async def test_user_flow(hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR) -> None:
    """Test successful user flow creates config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UnifiProtect"
    assert result["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_form_version_too_old(
    hass: HomeAssistant, bootstrap: Bootstrap, old_nvr: NVR, nvr: NVR, mock_setup: None
) -> None:
    """Test we handle the version being too old and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    bootstrap.nvr = old_nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "protect_version"}

    # Now test recovery with valid version
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "username": DEFAULT_USERNAME,
                "password": DEFAULT_PASSWORD,
                "api_key": DEFAULT_API_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)


async def test_form_invalid_auth_password(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR, mock_setup: None
) -> None:
    """Test we handle invalid auth password and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=NotAuthorized,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}

    # Now test recovery with valid credentials
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "username": DEFAULT_USERNAME,
                "password": "correct-password",
                "api_key": DEFAULT_API_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)


async def test_form_invalid_auth_api_key(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR, mock_setup: None
) -> None:
    """Test we handle invalid auth api key and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            side_effect=NotAuthorized,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"api_key": "invalid_auth"}

    # Now test recovery with valid API key
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "username": DEFAULT_USERNAME,
                "password": DEFAULT_PASSWORD,
                "api_key": "correct-api-key",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)


async def test_form_cloud_user(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    cloud_account: CloudAccount,
    nvr: NVR,
    mock_setup: None,
) -> None:
    """Test we handle cloud users and can recover with local user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user = bootstrap.users[bootstrap.auth_user_id]
    user.cloud_account = cloud_account
    bootstrap.users[bootstrap.auth_user_id] = user
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cloud_user"}

    # Now test recovery with local user
    user.cloud_account = None
    bootstrap.users[bootstrap.auth_user_id] = user
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "username": "local-username",
                "password": DEFAULT_PASSWORD,
                "api_key": DEFAULT_API_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)


async def test_form_cannot_connect(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR, mock_setup: None
) -> None:
    """Test we handle cannot connect error and can recover."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=NvrError,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            side_effect=NvrError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Now test recovery when connection works
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "username": DEFAULT_USERNAME,
                "password": DEFAULT_PASSWORD,
                "api_key": DEFAULT_API_KEY,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(nvr.mac)


async def test_form_reauth_auth(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
) -> None:
    """Test we handle reauth auth."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {
        "ip_address": "1.1.1.1",
        "name": "Mock Title",
    }

    # Verify that non-sensitive fields are pre-filled and sensitive fields are not
    # The data_schema will have been created with add_suggested_values_to_schema
    # We can't easily verify the suggested values, but we can verify the flow works
    # and that when only providing new credentials, the old non-sensitive data is kept

    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=NotAuthorized,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"password": "invalid_auth"}
    assert result["step_id"] == "reauth_confirm"

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new-password",
                "api_key": "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(mock_setup.mock_calls) == 1

    # Verify that non-sensitive data was preserved when only credentials were updated
    assert ufp_reauth_entry.data[CONF_HOST] == "1.1.1.1"
    assert ufp_reauth_entry.data[CONF_PORT] == 443
    assert ufp_reauth_entry.data[CONF_VERIFY_SSL] is False
    assert ufp_reauth_entry.data[CONF_USERNAME] == "test-username"
    assert ufp_reauth_entry.data[CONF_PASSWORD] == "new-password"
    assert ufp_reauth_entry.data[CONF_API_KEY] == "test-api-key"


async def test_form_options(
    hass: HomeAssistant,
    ufp_config_entry: MockConfigEntry,
    ufp_client: ProtectApiClient,
) -> None:
    """Test we handle options flows."""
    ufp_config_entry.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch("homeassistant.components.unifiprotect.async_start_discovery"),
        patch(
            "homeassistant.components.unifiprotect.utils.ProtectApiClient"
        ) as mock_api,
    ):
        mock_api.return_value = ufp_client

        await hass.config_entries.async_setup(ufp_config_entry.entry_id)
        await hass.async_block_till_done()
        assert ufp_config_entry.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(ufp_config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_DISABLE_RTSP: True,
                CONF_ALL_UPDATES: True,
                CONF_OVERRIDE_CHOST: True,
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            "all_updates": True,
            "disable_rtsp": True,
            "override_connection_host": True,
            "max_media": 1000,
        }
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(ufp_config_entry.entry_id)


@pytest.mark.parametrize(
    ("source", "data"),
    [
        (config_entries.SOURCE_DHCP, DHCP_DISCOVERY),
        (config_entries.SOURCE_SSDP, SSDP_DISCOVERY),
    ],
)
async def test_discovered_by_ssdp_or_dhcp(
    hass: HomeAssistant, source: str, data: DhcpServiceInfo | SsdpServiceInfo
) -> None:
    """Test we handoff to unifi-discovery when discovered via ssdp or dhcp."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": source},
            data=data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"


async def test_discovered_by_unifi_discovery_direct_connect(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
) -> None:
    """Test a discovery from unifi-discovery."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {
        "ip_address": DEVICE_IP_ADDRESS,
        "name": DEVICE_HOSTNAME,
    }

    assert not result["errors"]

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UnifiProtect"
    assert result["data"] == {
        "host": DIRECT_CONNECT_DOMAIN,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": True,
    }
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_discovered_by_unifi_discovery_direct_connect_updated(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery updates the direct connect host."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "y.ui.direct",
            CONF_USERNAME: DEFAULT_USERNAME,
            CONF_PASSWORD: DEFAULT_PASSWORD,
            CONF_API_KEY: DEFAULT_API_KEY,
            "id": "UnifiProtect",
            CONF_PORT: DEFAULT_PORT,
            CONF_VERIFY_SSL: True,
        },
        version=2,
        unique_id=DEVICE_MAC_ADDRESS.replace(":", "").upper(),
    )
    mock_config.add_to_hass(hass)

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config.data[CONF_HOST] == DIRECT_CONNECT_DOMAIN


async def test_discovered_by_unifi_discovery_direct_connect_updated_but_not_using_direct_connect(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery updates the host but not direct connect if its not in use."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.2.2",
            "username": "test-username",
            "password": "test-password",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
        },
        version=2,
        unique_id=DEVICE_MAC_ADDRESS.replace(":", "").upper(),
    )
    mock_config.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.unifiprotect.config_flow.async_console_is_alive",
            return_value=False,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config.data[CONF_HOST] == "127.0.0.1"


async def test_discovered_by_unifi_discovery_does_not_update_ip_when_console_is_still_online(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery does not update the ip unless the console at the old ip is offline."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.2.2.2",
            "username": "test-username",
            "password": "test-password",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
        },
        version=2,
        unique_id=DEVICE_MAC_ADDRESS.replace(":", "").upper(),
    )
    mock_config.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch(
            "homeassistant.components.unifiprotect.config_flow.async_console_is_alive",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config.data[CONF_HOST] == "1.2.2.2"


async def test_discovered_host_not_updated_if_existing_is_a_hostname(
    hass: HomeAssistant,
) -> None:
    """Test we only update the host if its an ip address from discovery."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "a.hostname",
            "username": "test-username",
            "password": "test-password",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id=DEVICE_MAC_ADDRESS.upper().replace(":", ""),
    )
    mock_config.add_to_hass(hass)

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config.data[CONF_HOST] == "a.hostname"


async def test_discovered_by_unifi_discovery(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
) -> None:
    """Test a discovery from unifi-discovery."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {
        "ip_address": DEVICE_IP_ADDRESS,
        "name": DEVICE_HOSTNAME,
    }

    assert not result["errors"]

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=[NotAuthorized, bootstrap],
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UnifiProtect"
    assert result["data"] == {
        "host": DEVICE_IP_ADDRESS,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_discovered_by_unifi_discovery_partial(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
) -> None:
    """Test a discovery from unifi-discovery partial."""

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT_PARTIAL,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {
        "ip_address": DEVICE_IP_ADDRESS,
        "name": "NVR DDEEFF",
    }

    assert not result["errors"]

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UnifiProtect"
    assert result["data"] == {
        "host": DEVICE_IP_ADDRESS,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_discovered_by_unifi_discovery_direct_connect_on_different_interface(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery from an alternate interface."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": DIRECT_CONNECT_DOMAIN,
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id="FFFFFFAAAAAA",
    )
    mock_config.add_to_hass(hass)

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_by_unifi_discovery_direct_connect_on_different_interface_ip_matches(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery from an alternate interface when the ip matches."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "127.0.0.1",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id="FFFFFFAAAAAA",
    )
    mock_config.add_to_hass(hass)

    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_by_unifi_discovery_direct_connect_on_different_interface_resolver(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery from an alternate interface when direct connect domain resolves to host ip."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "y.ui.direct",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id="FFFFFFAAAAAA",
    )
    mock_config.add_to_hass(hass)

    other_ip_dict = UNIFI_DISCOVERY_DICT.copy()
    other_ip_dict["source_ip"] = "127.0.0.1"
    other_ip_dict["direct_connect_domain"] = "nomatchsameip.ui.direct"

    with (
        _patch_discovery(),
        patch.object(
            hass.loop,
            "getaddrinfo",
            return_value=[(socket.AF_INET, None, None, None, ("127.0.0.1", 443))],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=other_ip_dict,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovered_by_unifi_discovery_direct_connect_on_different_interface_resolver_fails(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
) -> None:
    """Test we can still configure if the resolver fails."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "y.ui.direct",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id="FFFFFFAAAAAA",
    )
    mock_config.runtime_data = Mock(async_stop=AsyncMock())
    mock_config.add_to_hass(hass)

    other_ip_dict = UNIFI_DISCOVERY_DICT.copy()
    other_ip_dict["source_ip"] = "127.0.0.2"
    other_ip_dict["direct_connect_domain"] = "nomatchsameip.ui.direct"

    with (
        _patch_discovery(),
        patch.object(hass.loop, "getaddrinfo", side_effect=OSError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=other_ip_dict,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flows[0]["context"]["title_placeholders"] == {
        "ip_address": "127.0.0.2",
        "name": "unvr",
    }

    assert not result["errors"]

    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UnifiProtect"
    assert result["data"] == {
        "host": "nomatchsameip.ui.direct",
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": True,
    }
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )
    assert len(mock_setup_entry.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1


async def test_discovered_by_unifi_discovery_direct_connect_on_different_interface_resolver_no_result(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery from an alternate interface when direct connect domain resolve has no result."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "y.ui.direct",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": True,
        },
        unique_id="FFFFFFAAAAAA",
    )
    mock_config.add_to_hass(hass)

    other_ip_dict = UNIFI_DISCOVERY_DICT.copy()
    other_ip_dict["source_ip"] = "127.0.0.2"
    other_ip_dict["direct_connect_domain"] = "y.ui.direct"

    with _patch_discovery(), patch.object(hass.loop, "getaddrinfo", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=other_ip_dict,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_can_be_ignored(hass: HomeAssistant) -> None:
    """Test a discovery can be ignored."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=DEVICE_MAC_ADDRESS.upper().replace(":", ""),
        source=config_entries.SOURCE_IGNORE,
    )
    mock_config.add_to_hass(hass)
    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_discovery_with_both_ignored_and_normal_entry(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
) -> None:
    """Test discovery skips ignored entries with different MAC and completes."""
    # Create ignored entry with different MAC - should be skipped (line 182)
    # Use a completely different MAC that won't match discovery MAC (AABBCCDDEEFF)
    other_mac = "11:22:33:44:55:66"
    mock_ignored = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id=other_mac.replace(":", "").upper(),  # 112233445566
        source=config_entries.SOURCE_IGNORE,
    )
    mock_ignored.add_to_hass(hass)

    # Create second ignored entry with different MAC - should also be skipped
    other_mac2 = "22:33:44:55:66:77"
    mock_ignored2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.5"},
        unique_id=other_mac2.replace(":", "").upper(),  # 223344556677
        source=config_entries.SOURCE_IGNORE,
    )
    mock_ignored2.add_to_hass(hass)

    # Discovery should:
    # 1. Skip all ignored entries with different MAC (line 182 - continue)
    # 2. Continue to discovery flow since no matching entries
    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    # Flow continues to discovery step since no match found
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Complete the flow
    bootstrap.nvr = nvr
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            return_value=bootstrap,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": DEFAULT_USERNAME,
                "password": DEFAULT_PASSWORD,
                "api_key": DEFAULT_API_KEY,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )


async def test_discovery_confirm_fallback_to_ip(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test discovery confirm falls back to IP when direct connect fails."""
    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    bootstrap.nvr = nvr
    # First call (direct connect) fails, second call (IP) succeeds
    mock_api_bootstrap.side_effect = [NvrError("Direct connect failed"), bootstrap]

    with (
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == DEVICE_IP_ADDRESS
    assert result["data"]["verify_ssl"] is False
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )


async def test_discovery_confirm_with_api_key_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test discovery confirm preserves API key in form data on error."""
    with _patch_discovery():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data=UNIFI_DISCOVERY_DICT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    # Both attempts fail to test form_data preservation with API key
    mock_api_bootstrap.side_effect = NvrError("Connection failed")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    # Now provide working connection to complete the flow
    bootstrap.nvr = nvr
    mock_api_bootstrap.side_effect = None
    mock_api_bootstrap.return_value = bootstrap

    with (
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == _async_unifi_mac_from_hass(
        DEVICE_MAC_ADDRESS.upper().replace(":", "")
    )


async def test_reconfigure(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Test with connection error
    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    mock_api_bootstrap.side_effect = [NvrError, bootstrap]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **RECONFIGURE_USER_INPUT,
            CONF_HOST: "1.1.1.2",
            CONF_PASSWORD: "new-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test successful reconfiguration with matching NVR MAC
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **RECONFIGURE_USER_INPUT,
            CONF_HOST: "1.1.1.2",
            CONF_PASSWORD: "new-password",
            CONF_API_KEY: "new-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert ufp_reauth_entry.data[CONF_HOST] == "1.1.1.2"
    assert ufp_reauth_entry.data[CONF_PASSWORD] == "new-password"
    assert ufp_reauth_entry.data[CONF_API_KEY] == "new-api-key"


async def test_reconfigure_different_nvr(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test reconfiguration flow aborts when trying to switch to different NVR."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Create a different NVR with different MAC (not matching MAC_ADDR)
    different_nvr = nvr.model_copy()
    different_nvr.mac = "112233445566"  # Different from MAC_ADDR
    bootstrap.nvr = different_nvr

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **BASE_USER_INPUT,
            CONF_HOST: "2.2.2.2",
            CONF_USERNAME: "different-username",
            CONF_PASSWORD: "different-password",
            CONF_API_KEY: "different-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_nvr"
    # Verify original config wasn't modified
    assert ufp_reauth_entry.unique_id == _async_unifi_mac_from_hass(MAC_ADDR)
    assert ufp_reauth_entry.data[CONF_HOST] == "1.1.1.1"


async def test_reconfigure_auth_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow with authentication error."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Test with password authentication error
    mock_api_bootstrap.side_effect = NotAuthorized

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_USER_INPUT, CONF_PASSWORD: "wrong-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    # Now provide correct credentials to complete the flow
    result = await _complete_reconfigure_flow(
        hass, result["flow_id"], nvr, bootstrap, mock_api_bootstrap, mock_api_meta_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_api_key_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow with API key error."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    # Test with API key authentication error
    mock_api_meta_info.side_effect = NotAuthorized

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**RECONFIGURE_USER_INPUT, CONF_API_KEY: "wrong-api-key"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_auth"}

    # Now provide correct API key to complete the flow
    result = await _complete_reconfigure_flow(
        hass, result["flow_id"], nvr, bootstrap, mock_api_bootstrap, mock_api_meta_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_cloud_user(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow with cloud user error."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Set up bootstrap with cloud user
    bootstrap.nvr = nvr
    bootstrap.users[bootstrap.auth_user_id].cloud_account = CloudAccount(
        user_id="cloud_id",
        id="cloud_id",
        name="Cloud User",
        email="user@example.com",
        first_name="Test",
        last_name="User",
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **BASE_USER_INPUT,
            CONF_USERNAME: "cloud-username",
            CONF_PASSWORD: "cloud-password",
            CONF_API_KEY: DEFAULT_API_KEY,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cloud_user"}

    # Now provide local user credentials to complete the flow
    bootstrap.users[bootstrap.auth_user_id].cloud_account = None
    result = await _complete_reconfigure_flow(
        hass, result["flow_id"], nvr, bootstrap, mock_api_bootstrap, mock_api_meta_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_outdated_version(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow with outdated protect version."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Set up NVR with outdated version
    old_nvr = nvr.model_copy()
    old_nvr.version = Version("5.0.0")  # Below MIN_REQUIRED_PROTECT_V (6.0.0)
    bootstrap.nvr = old_nvr

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        RECONFIGURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "protect_version"}

    # Now provide updated NVR version to complete the flow
    result = await _complete_reconfigure_flow(
        hass, result["flow_id"], nvr, bootstrap, mock_api_bootstrap, mock_api_meta_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_form_defaults(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry_alt: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow form has correct default values."""
    ufp_reauth_entry_alt.add_to_hass(hass)

    result = await ufp_reauth_entry_alt.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Verify that non-sensitive fields are pre-filled and sensitive fields are not
    # The data_schema will have been created with add_suggested_values_to_schema
    # We can't easily verify the suggested values, but we can verify the flow works
    # and that when only providing new credentials, the old non-sensitive data is kept

    # Use nvr with matching MAC
    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr

    # Complete the flow to verify it works
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "new-password",
            CONF_API_KEY: "new-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify that all data was updated
    entry = hass.config_entries.async_get_entry(ufp_reauth_entry_alt.entry_id)
    assert entry.data[CONF_HOST] == "1.1.1.1"
    assert entry.data[CONF_PORT] == 8443
    assert entry.data[CONF_VERIFY_SSL] is True
    assert entry.data[CONF_USERNAME] == "test-username"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_API_KEY] == "new-api-key"


async def test_reconfigure_same_nvr_updated_credentials(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration flow updating credentials for same NVR."""
    # Use the NVR's actual MAC address
    nvr_mac = _async_unifi_mac_from_hass(nvr.mac)

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "old-username",
            CONF_PASSWORD: "old-password",
            CONF_API_KEY: "old-api-key",
            "id": "UnifiProtect",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
        },
        unique_id=nvr_mac,
    )
    mock_config.add_to_hass(hass)

    result = await mock_config.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    bootstrap.nvr = nvr
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "2.2.2.2",
            CONF_PORT: 8443,
            CONF_VERIFY_SSL: True,
            CONF_USERNAME: "new-username",
            CONF_PASSWORD: "new-password",
            CONF_API_KEY: "new-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Verify unique_id remains the same
    assert mock_config.unique_id == nvr_mac
    # Verify credentials were updated
    assert mock_config.data[CONF_HOST] == "2.2.2.2"
    assert mock_config.data[CONF_PORT] == 8443
    assert mock_config.data[CONF_VERIFY_SSL] is True
    assert mock_config.data[CONF_USERNAME] == "new-username"
    assert mock_config.data[CONF_PASSWORD] == "new-password"
    assert mock_config.data[CONF_API_KEY] == "new-api-key"


async def test_reconfigure_empty_credentials_keeps_existing(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfiguration with empty credentials keeps existing values."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    # Submit with empty password and api_key - should keep existing values
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            **BASE_USER_INPUT,
            CONF_HOST: "2.2.2.2",
            CONF_PASSWORD: "",  # Empty - should keep existing
            CONF_API_KEY: "",  # Empty - should keep existing
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Verify existing credentials were preserved
    assert ufp_reauth_entry.data[CONF_HOST] == "2.2.2.2"
    assert ufp_reauth_entry.data[CONF_PASSWORD] == "test-password"
    assert ufp_reauth_entry.data[CONF_API_KEY] == "test-api-key"


@pytest.mark.parametrize(
    ("input_credentials", "expected_credentials"),
    [
        # Only password updated, api_key kept
        (
            {CONF_PASSWORD: "new-password", CONF_API_KEY: ""},
            {CONF_PASSWORD: "new-password", CONF_API_KEY: "test-api-key"},
        ),
        # Only api_key updated, password kept
        (
            {CONF_PASSWORD: "", CONF_API_KEY: "new-api-key"},
            {CONF_PASSWORD: "test-password", CONF_API_KEY: "new-api-key"},
        ),
        # Both credentials updated
        (
            {CONF_PASSWORD: "new-password", CONF_API_KEY: "new-api-key"},
            {CONF_PASSWORD: "new-password", CONF_API_KEY: "new-api-key"},
        ),
    ],
    ids=["password_only", "api_key_only", "both_credentials"],
)
async def test_reconfigure_credential_update(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
    input_credentials: dict[str, str],
    expected_credentials: dict[str, str],
) -> None:
    """Test reconfiguration with various credential update scenarios."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**BASE_USER_INPUT, **input_credentials},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert ufp_reauth_entry.data[CONF_PASSWORD] == expected_credentials[CONF_PASSWORD]
    assert ufp_reauth_entry.data[CONF_API_KEY] == expected_credentials[CONF_API_KEY]


async def test_reconfigure_invalid_existing_password_shows_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfigure shows password error when existing password is invalid."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM

    # Simulate invalid existing password (user leaves field empty)
    mock_api_bootstrap.side_effect = NotAuthorized

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**BASE_USER_INPUT, CONF_PASSWORD: "", CONF_API_KEY: ""},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

    # Now provide correct credentials to complete the flow
    result = await _complete_reconfigure_flow(
        hass, result["flow_id"], nvr, bootstrap, mock_api_bootstrap, mock_api_meta_info
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reauth_empty_credentials_keeps_existing(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test reauth with empty credentials keeps existing values."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    with patch(
        "homeassistant.components.unifiprotect.async_setup",
        return_value=True,
    ):
        # Submit with empty credentials - should keep existing
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "",  # Empty - should keep existing
                CONF_API_KEY: "",  # Empty - should keep existing
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Verify existing credentials were preserved
    assert ufp_reauth_entry.data[CONF_PASSWORD] == "test-password"
    assert ufp_reauth_entry.data[CONF_API_KEY] == "test-api-key"


@pytest.mark.parametrize(
    ("input_credentials", "expected_credentials"),
    [
        # Only password updated, api_key kept
        (
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "",
            },
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "test-api-key",
            },
        ),
        # Only api_key updated, password kept
        (
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "",
                CONF_API_KEY: "new-api-key",
            },
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_API_KEY: "new-api-key",
            },
        ),
        # All credentials updated
        (
            {
                CONF_USERNAME: "new-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "new-api-key",
            },
            {
                CONF_USERNAME: "new-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "new-api-key",
            },
        ),
    ],
    ids=["password_only", "api_key_only", "all_credentials"],
)
async def test_reauth_credential_update(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    input_credentials: dict[str, str],
    expected_credentials: dict[str, str],
) -> None:
    """Test reauth with various credential update scenarios."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr
    with patch(
        "homeassistant.components.unifiprotect.async_setup",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            input_credentials,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert ufp_reauth_entry.data[CONF_USERNAME] == expected_credentials[CONF_USERNAME]
    assert ufp_reauth_entry.data[CONF_PASSWORD] == expected_credentials[CONF_PASSWORD]
    assert ufp_reauth_entry.data[CONF_API_KEY] == expected_credentials[CONF_API_KEY]
    # Host should remain unchanged
    assert ufp_reauth_entry.data[CONF_HOST] == "1.1.1.1"


async def test_reconfigure_clears_session_failure_continues(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reauth_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
    mock_setup: AsyncMock,
) -> None:
    """Test reconfigure continues even if session clearing fails."""
    ufp_reauth_entry.add_to_hass(hass)

    result = await ufp_reauth_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
    bootstrap.nvr = nvr

    # Simulate session clear failure - should still continue
    with patch(
        "homeassistant.components.unifiprotect.config_flow.async_create_api_client"
    ) as mock_create_client:
        mock_protect = AsyncMock()
        mock_protect.clear_session = AsyncMock(side_effect=Exception("Session error"))
        mock_create_client.return_value = mock_protect

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "new-username",  # Changed
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "new-api-key",
            },
        )
        await hass.async_block_till_done()

    # Should still succeed despite session clear failure
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert ufp_reauth_entry.data[CONF_USERNAME] == "new-username"
    assert ufp_reauth_entry.data[CONF_PASSWORD] == "new-password"


async def test_form_api_key_client_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
) -> None:
    """Test that ClientError during API key validation shows cannot_connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    bootstrap.nvr = nvr

    with patch(
        "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
        side_effect=ClientError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_port_int_conversion(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test that port value is converted to int (NumberSelector returns float)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    bootstrap.nvr = nvr

    with (
        patch(
            "homeassistant.components.unifiprotect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.unifiprotect.async_setup",
            return_value=True,
        ),
    ):
        # NumberSelector returns float, verify int conversion works
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8443.0,  # Float from NumberSelector
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_API_KEY: "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == 8443
    assert isinstance(result["data"][CONF_PORT], int)
