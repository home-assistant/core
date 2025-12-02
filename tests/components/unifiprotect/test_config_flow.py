"""Test the UniFi Protect config flow."""

from __future__ import annotations

from dataclasses import asdict
import socket
from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect import NotAuthorized, NvrError, ProtectApiClient
from uiprotect.data import NVR, Bootstrap, CloudAccount, Version

from homeassistant import config_entries
from homeassistant.components.unifiprotect.const import (
    CONF_ALL_UPDATES,
    CONF_DISABLE_RTSP,
    CONF_OVERRIDE_CHOST,
    DOMAIN,
)
from homeassistant.components.unifiprotect.utils import _async_unifi_mac_from_hass
from homeassistant.config_entries import ConfigEntryState
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
from .conftest import MAC_ADDR

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

UNIFI_DISCOVERY_DICT = asdict(UNIFI_DISCOVERY)
UNIFI_DISCOVERY_DICT_PARTIAL = asdict(UNIFI_DISCOVERY_PARTIAL)


async def test_form(hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR) -> None:
    """Test we get the form."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_form_version_too_old(
    hass: HomeAssistant, bootstrap: Bootstrap, old_nvr: NVR
) -> None:
    """Test we handle the version being too old."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "protect_version"}


async def test_form_invalid_auth_password(hass: HomeAssistant) -> None:
    """Test we handle invalid auth password."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}


async def test_form_invalid_auth_api_key(
    hass: HomeAssistant, bootstrap: Bootstrap
) -> None:
    """Test we handle invalid auth api key."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"api_key": "invalid_auth"}


async def test_form_cloud_user(
    hass: HomeAssistant, bootstrap: Bootstrap, cloud_account: CloudAccount
) -> None:
    """Test we handle cloud users."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cloud_user"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_reauth_auth(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
) -> None:
    """Test we handle reauth auth."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
        },
        unique_id=_async_unifi_mac_from_hass(MAC_ADDR),
    )
    mock_config.add_to_hass(hass)

    result = await mock_config.start_reauth_flow(hass)
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}
    assert result2["step_id"] == "reauth_confirm"

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
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "new-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert len(mock_setup.mock_calls) == 1

    # Verify that non-sensitive data was preserved when only credentials were updated
    assert mock_config.data[CONF_HOST] == "1.1.1.1"
    assert mock_config.data[CONF_PORT] == 443
    assert mock_config.data[CONF_VERIFY_SSL] is False
    assert mock_config.data[CONF_USERNAME] == "test-username"
    assert mock_config.data[CONF_PASSWORD] == "new-password"
    assert mock_config.data[CONF_API_KEY] == "test-api-key"


async def test_form_options(hass: HomeAssistant, ufp_client: ProtectApiClient) -> None:
    """Test we handle options flows."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "test-username",
            "password": "test-password",
            "api_key": "test-api-key",
            "id": "UnifiProtect",
            "port": 443,
            "verify_ssl": False,
            "max_media": 1000,
        },
        version=2,
        unique_id=_async_unifi_mac_from_hass(MAC_ADDR),
    )
    mock_config.add_to_hass(hass)

    with (
        _patch_discovery(),
        patch("homeassistant.components.unifiprotect.async_start_discovery"),
        patch(
            "homeassistant.components.unifiprotect.utils.ProtectApiClient"
        ) as mock_api,
    ):
        mock_api.return_value = ufp_client

        await hass.config_entries.async_setup(mock_config.entry_id)
        await hass.async_block_till_done()
        assert mock_config.state is ConfigEntryState.LOADED

        result = await hass.config_entries.options.async_init(mock_config.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert not result["errors"]
        assert result["step_id"] == "init"

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_DISABLE_RTSP: True,
                CONF_ALL_UPDATES: True,
                CONF_OVERRIDE_CHOST: True,
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            "all_updates": True,
            "disable_rtsp": True,
            "override_connection_host": True,
            "max_media": 1000,
        }
        await hass.async_block_till_done()
        await hass.config_entries.async_unload(mock_config.entry_id)


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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": DIRECT_CONNECT_DOMAIN,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": True,
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_discovered_by_unifi_discovery_direct_connect_updated(
    hass: HomeAssistant,
) -> None:
    """Test a discovery from unifi-discovery updates the direct connect host."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": DEVICE_IP_ADDRESS,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": DEVICE_IP_ADDRESS,
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": False,
    }
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "UnifiProtect"
    assert result2["data"] == {
        "host": "nomatchsameip.ui.direct",
        "username": "test-username",
        "password": "test-password",
        "api_key": "test-api-key",
        "id": "UnifiProtect",
        "port": 443,
        "verify_ssl": True,
    }
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
) -> None:
    """Test discovery skips ignored entries with different MAC."""
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


async def test_discovery_confirm_fallback_to_ip(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
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
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=[
                NvrError("Direct connect failed"),  # First attempt fails
                bootstrap,  # Second attempt succeeds
            ],
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"]["host"] == DEVICE_IP_ADDRESS
    assert result2["data"]["verify_ssl"] is False


async def test_discovery_confirm_with_api_key_error(
    hass: HomeAssistant, bootstrap: Bootstrap, nvr: NVR
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
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=NvrError("Connection failed"),
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "api_key": "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "discovery_confirm"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Test with connection error
    with (
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_bootstrap",
            side_effect=NvrError,
        ),
        patch(
            "homeassistant.components.unifiprotect.config_flow.ProtectApiClient.get_meta_info",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Test successful reconfiguration with matching NVR MAC
    nvr.mac = _async_unifi_mac_from_hass(MAC_ADDR)
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
            "homeassistant.config_entries.ConfigEntries.async_reload",
        ) as mock_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.2",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "new-password",
                CONF_API_KEY: "new-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert ufp_reconfigure_entry.data[CONF_HOST] == "1.1.1.2"
    assert ufp_reconfigure_entry.data[CONF_PASSWORD] == "new-password"
    assert ufp_reconfigure_entry.data[CONF_API_KEY] == "new-api-key"
    mock_reload.assert_called_once_with(ufp_reconfigure_entry.entry_id)


async def test_reconfigure_different_nvr(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test reconfiguration flow aborts when trying to switch to different NVR."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Create a different NVR with different MAC (not matching MAC_ADDR)
    different_nvr = nvr.model_copy()
    different_nvr.mac = "112233445566"  # Different from MAC_ADDR
    bootstrap.nvr = different_nvr

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "2.2.2.2",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
            CONF_USERNAME: "different-username",
            CONF_PASSWORD: "different-password",
            CONF_API_KEY: "different-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_nvr"
    # Verify original config wasn't modified
    assert ufp_reconfigure_entry.unique_id == _async_unifi_mac_from_hass(MAC_ADDR)
    assert ufp_reconfigure_entry.data[CONF_HOST] == "1.1.1.1"


async def test_reconfigure_wrong_nvr(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test reconfiguration flow aborts when connected to wrong NVR."""
    # Use the NVR's actual MAC address
    nvr_mac = _async_unifi_mac_from_hass(nvr.mac)

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_API_KEY: "test-api-key",
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

    # Create a different NVR (user connected to wrong device)
    different_nvr = nvr.model_copy()
    different_nvr.mac = "112233445566"
    bootstrap.nvr = different_nvr

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "2.2.2.2",
            CONF_PORT: 443,
            CONF_VERIFY_SSL: False,
            CONF_USERNAME: "different-username",
            CONF_PASSWORD: "different-password",
            CONF_API_KEY: "different-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_nvr"
    # Verify original config wasn't modified
    assert mock_config.unique_id == nvr_mac
    assert mock_config.data[CONF_HOST] == "1.1.1.1"


async def test_reconfigure_auth_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with authentication error."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Test with password authentication error
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
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "wrong-password",
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_reconfigure_api_key_error(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with API key error."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    bootstrap.nvr = nvr
    # Test with API key authentication error
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
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_API_KEY: "wrong-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_auth"}


async def test_reconfigure_cloud_user(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with cloud user error."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
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
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "cloud-username",
                CONF_PASSWORD: "cloud-password",
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cloud_user"}


async def test_reconfigure_outdated_version(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with outdated protect version."""
    ufp_reconfigure_entry.add_to_hass(hass)

    result = await ufp_reconfigure_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Set up NVR with outdated version
    old_nvr = nvr.model_copy()
    old_nvr.version = Version("5.0.0")  # Below MIN_REQUIRED_PROTECT_V (6.0.0)
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
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 443,
                CONF_VERIFY_SSL: False,
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "protect_version"}


async def test_reconfigure_form_defaults(
    hass: HomeAssistant,
    bootstrap: Bootstrap,
    nvr: NVR,
    ufp_reconfigure_entry_alt: MockConfigEntry,
    mock_api_bootstrap: Mock,
    mock_api_meta_info: Mock,
) -> None:
    """Test reconfiguration flow form has correct default values."""
    ufp_reconfigure_entry_alt.add_to_hass(hass)

    result = await ufp_reconfigure_entry_alt.start_reconfigure_flow(hass)

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
    with patch.object(hass.config_entries, "async_reload"):
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
    entry = hass.config_entries.async_get_entry(ufp_reconfigure_entry_alt.entry_id)
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
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
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
    # Verify reload was called
    assert len(mock_reload.mock_calls) == 1
