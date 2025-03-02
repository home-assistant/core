"""Test the Velux config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pyvlx import PyVLXException

from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="127.0.0.1",
    hostname="VELUX_KLF_LAN_ABCD",
    macaddress="64618400abcd",
)


async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_velux_client: AsyncMock,
) -> None:
    """Test starting a flow by user with valid values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "127.0.0.1"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "NotAStrongPassword",
    }
    assert not result["result"].unique_id

    mock_velux_client.disconnect.assert_called_once()
    mock_velux_client.connect.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PyVLXException("DUMMY"), "cannot_connect"),
        (Exception("DUMMY"), "unknown"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant,
    mock_velux_client: AsyncMock,
    exception: Exception,
    error: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test starting a flow by user but with exceptions."""

    mock_velux_client.connect.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_velux_client.connect.assert_called_once()

    mock_velux_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_user_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test initialized flow with a duplicate entry."""
    mock_user_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_velux_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we can setup from dhcp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "NotAStrongPassword"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "VELUX_KLF_ABCD"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_MAC: "64:61:84:00:ab:cd",
        CONF_NAME: "VELUX_KLF_ABCD",
        CONF_PASSWORD: "NotAStrongPassword",
    }
    assert result["result"].unique_id == "VELUX_KLF_ABCD"

    mock_velux_client.disconnect.assert_called()
    mock_velux_client.connect.assert_called()


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (PyVLXException("DUMMY"), "cannot_connect"),
        (Exception("DUMMY"), "unknown"),
    ],
)
async def test_dhcp_discovery_errors(
    hass: HomeAssistant,
    mock_velux_client: AsyncMock,
    exception: Exception,
    error: str,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we can setup from dhcp discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    mock_velux_client.connect.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "NotAStrongPassword"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["errors"] == {"base": error}

    mock_velux_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "NotAStrongPassword"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "VELUX_KLF_ABCD"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_MAC: "64:61:84:00:ab:cd",
        CONF_NAME: "VELUX_KLF_ABCD",
        CONF_PASSWORD: "NotAStrongPassword",
    }


async def test_dhcp_discovery_already_configured(
    hass: HomeAssistant,
    mock_velux_client: AsyncMock,
    mock_discovered_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test dhcp discovery when already configured."""
    mock_discovered_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discover_unique_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_velux_client: AsyncMock,
    mock_user_config_entry: MockConfigEntry,
) -> None:
    """Test dhcp discovery when already configured."""
    mock_user_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_user_config_entry.entry_id)

    assert mock_user_config_entry.state is ConfigEntryState.LOADED
    assert mock_user_config_entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_user_config_entry.unique_id == "VELUX_KLF_ABCD"


async def test_dhcp_discovery_not_loaded(
    hass: HomeAssistant,
    mock_velux_client: AsyncMock,
    mock_user_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test dhcp discovery when entry with same host not loaded."""
    mock_user_config_entry.add_to_hass(hass)

    assert mock_user_config_entry.state is not ConfigEntryState.LOADED
    assert mock_user_config_entry.unique_id is None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_user_config_entry.unique_id is None
