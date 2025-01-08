"""Test the Velux config flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import patch

import pytest
from pyvlx import PyVLXException

from homeassistant.components.dhcp import DhcpServiceInfo
from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

DUMMY_DATA: dict[str, Any] = {
    CONF_NAME: "VELUX_KLF_ABCD",
    CONF_HOST: "127.0.0.1",
    CONF_PASSWORD: "NotAStrongPassword",
}

PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH = (
    "homeassistant.components.velux.config_flow.PyVLX.connect"
)
PYVLX_CONFIG_FLOW_CLASS_PATH = "homeassistant.components.velux.config_flow.PyVLX"

error_types_to_test: list[tuple[Exception, str]] = [
    (PyVLXException("DUMMY"), "cannot_connect"),
    (Exception("DUMMY"), "unknown"),
]

pytest.mark.usefixtures("mock_setup_entry")


async def test_user_success(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True) as client_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        client_mock.return_value.disconnect.assert_called_once()
        client_mock.return_value.connect.assert_called_once()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == DUMMY_DATA[CONF_NAME]
        assert result["data"] == DUMMY_DATA


@pytest.mark.parametrize(("error", "error_name"), error_types_to_test)
async def test_user_errors(
    hass: HomeAssistant, error: Exception, error_name: str
) -> None:
    """Test starting a flow by user but with exceptions."""
    with patch(
        PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH, side_effect=error
    ) as connect_mock:
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=deepcopy(DUMMY_DATA)
        )

        connect_mock.assert_called_once()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_name}


async def test_flow_duplicate_entry(hass: HomeAssistant) -> None:
    """Test initialized flow with a duplicate entry."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title=DUMMY_DATA[CONF_HOST], data=DUMMY_DATA
        )

        conf_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=DUMMY_DATA,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test we can setup from dhcp discovery."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=DhcpServiceInfo(
                ip="127.0.0.1",
                hostname="VELUX_KLF_LAN_ABCD",
                macaddress="6461800122",
            ),
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"


async def test_dhcp_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test dhcp discovery when already configured."""
    # Setup entry.
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data=DUMMY_DATA,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id is None
    await hass.async_block_till_done()

    # Set unique_id for already configured entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip=DUMMY_DATA[CONF_HOST],
            hostname="VELUX_KLF_LAN_ABCD",
            macaddress="64:61:84:00:AB:CD",
        ),
    )
    assert result["type"] == FlowResultType.ABORT
    assert (
        hass.config_entries.async_entries(DOMAIN)[0].unique_id == DUMMY_DATA[CONF_NAME]
    )
    assert result["reason"] == "already_configured"

    # Update ip address of already configured unique_id.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="127.1.1.2",
            hostname="VELUX_KLF_LAN_ABCD",
            macaddress="64:61:84:00:AB:CD",
        ),
    )
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == "127.1.1.2"
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
