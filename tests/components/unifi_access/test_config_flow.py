"""Tests for the UniFi Access config flow."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unifi_access_api import ApiAuthError, ApiConnectionError
from unifi_discovery import UnifiDevice, UnifiService

from homeassistant.components.unifi_access.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_SSDP,
    SOURCE_USER,
)
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_DESCRIPTION,
    SsdpServiceInfo,
)

from .conftest import MOCK_API_TOKEN, MOCK_HOST

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi Access"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_API_TOKEN: MOCK_API_TOKEN,
        CONF_VERIFY_SSL: False,
    }
    mock_client.authenticate.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiConnectionError("Connection failed"), "cannot_connect"),
        (ApiAuthError(), "invalid_auth"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user config flow errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_client.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user config flow aborts when already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_different_host(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user config flow allows different host."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"
    assert mock_config_entry.data[CONF_HOST] == MOCK_HOST
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiConnectionError("Connection failed"), "cannot_connect"),
        (ApiAuthError(), "invalid_auth"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_client.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "new-api-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: "new-api-token",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "10.0.0.1"
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is True


async def test_reconfigure_flow_same_host_new_token(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow with same host and new API token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: MOCK_HOST,
            CONF_API_TOKEN: "new-api-token",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == MOCK_HOST
    assert mock_config_entry.data[CONF_API_TOKEN] == "new-api-token"


async def test_reconfigure_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration flow aborts when host already configured."""
    mock_config_entry.add_to_hass(hass)

    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: "other-token",
            CONF_VERIFY_SSL: False,
        },
    )
    other_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: "new-api-token",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (ApiConnectionError("Connection failed"), "cannot_connect"),
        (ApiAuthError(), "invalid_auth"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test reconfiguration flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_client.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: "new-api-token",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_client.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "10.0.0.1",
            CONF_API_TOKEN: "new-api-token",
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


DHCP_DISCOVERY = DhcpServiceInfo(
    ip="10.0.0.5",
    hostname="UniFi-Dream-Machine",
    macaddress="b4fbe4aabbcc",
)

SSDP_DISCOVERY = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    upnp={
        ATTR_UPNP_MANUFACTURER: "Ubiquiti Networks",
        ATTR_UPNP_MODEL_DESCRIPTION: "UniFi Dream Machine Pro",
    },
)


def _make_discovered_device(
    source_ip: str = "10.0.0.5",
    hw_addr: str = "b4:fb:e4:aa:bb:cc",
    hostname: str = "UniFi-Dream-Machine",
    platform: str = "UDMPRO",
) -> UnifiDevice:
    """Create a mock UnifiDevice with Access enabled."""
    device = UnifiDevice(
        source_ip=source_ip,
        hw_addr=hw_addr,
        hostname=hostname,
        platform=platform,
    )
    device.services[UnifiService.Access] = True
    return device


async def test_dhcp_discovery(
    hass: HomeAssistant,
) -> None:
    """Test DHCP discovery triggers background discovery and aborts."""
    with patch(
        "homeassistant.components.unifi_access.config_flow.async_start_discovery"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"


async def test_ssdp_discovery(
    hass: HomeAssistant,
) -> None:
    """Test SSDP discovery triggers background discovery and aborts."""
    with patch(
        "homeassistant.components.unifi_access.config_flow.async_start_discovery"
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "discovery_started"


async def test_integration_discovery_new_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
) -> None:
    """Test integration discovery shows confirm form for new device."""
    device = _make_discovered_device()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=asdict(device),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi Access"
    assert result["data"][CONF_HOST] == "10.0.0.5"
    assert result["data"][CONF_API_TOKEN] == MOCK_API_TOKEN
    assert result["data"][CONF_VERIFY_SSL] is False


async def test_integration_discovery_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration discovery aborts when host already configured."""
    mock_config_entry.add_to_hass(hass)

    device = _make_discovered_device(source_ip=MOCK_HOST)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=asdict(device),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_integration_discovery_updates_host(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration discovery updates host when IP changes."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="B4FBE4AABBCC")

    device = _make_discovered_device(source_ip="10.0.0.99")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=asdict(device),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "10.0.0.99"


async def test_integration_discovery_confirm_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_client: MagicMock,
) -> None:
    """Test integration discovery confirm handles auth errors."""
    device = _make_discovered_device()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data=asdict(device),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    mock_client.authenticate.side_effect = ApiAuthError()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "bad-token",
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: MOCK_API_TOKEN,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
