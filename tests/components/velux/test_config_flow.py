"""Test the Velux config flow."""

from __future__ import annotations

from copy import deepcopy
from ipaddress import ip_address
from typing import Any
from unittest.mock import patch

import pytest
from pyvlx import PyVLXException
from pyvlx.discovery import VeluxHost

from homeassistant.components import zeroconf
from homeassistant.components.velux import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_UNIGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import HOST, HOSTNAME, PASSWORD

from tests.common import MockConfigEntry

DUMMY_DATA: dict[str, Any] = {
    CONF_HOST: HOST,
    CONF_PASSWORD: PASSWORD,
}

PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH = (
    "homeassistant.components.velux.config_flow.PyVLX.connect"
)
PYVLX_CONFIG_FLOW_CLASS_PATH = "homeassistant.components.velux.config_flow.PyVLX"

error_types_to_test: list[tuple[Exception, str]] = [
    (PyVLXException("DUMMY"), "cannot_connect"),
    (Exception("DUMMY"), "unknown"),
]

pytestmark = pytest.mark.usefixtures(
    "mock_setup_entry", "mock_async_zeroconf", "mock_velux_discovery"
)


async def test_user_success(hass: HomeAssistant) -> None:
    """Test starting a flow by user with valid values."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True) as client_mock, patch(
        "pyvlx.discovery.VeluxDiscovery.hosts",
        [VeluxHost(hostname=HOSTNAME, ip_address=HOST)],
    ):
        result: dict[str, Any] = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=None
        )
        assert result["type"] == FlowResultType.FORM

        result2: dict[str, Any] = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=deepcopy(DUMMY_DATA)
        )
        client_mock.return_value.disconnect.assert_called_once()
        client_mock.return_value.connect.assert_called_once()
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == DUMMY_DATA[CONF_HOST]
        assert result2["data"] == DUMMY_DATA
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1
        assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == HOSTNAME


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

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": error_name}


async def test_import_valid_config(hass: HomeAssistant) -> None:
    """Test import initialized flow with valid config."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == DUMMY_DATA[CONF_HOST]
        assert result["data"] == DUMMY_DATA


@pytest.mark.parametrize("flow_source", [SOURCE_IMPORT, SOURCE_USER])
async def test_flow_duplicate_entry(hass: HomeAssistant, flow_source: str) -> None:
    """Test import initialized flow with a duplicate entry."""
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title=DUMMY_DATA[CONF_HOST], data=DUMMY_DATA
        )

        conf_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": flow_source},
            data=DUMMY_DATA,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("error", "error_name"), error_types_to_test)
async def test_import_errors(
    hass: HomeAssistant, error: Exception, error_name: str
) -> None:
    """Test import initialized flow with exceptions."""
    with patch(
        PYVLX_CONFIG_FLOW_CONNECT_FUNCTION_PATH,
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == error_name


async def test_unignore_step(hass: HomeAssistant) -> None:
    """Test the unignore step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_UNIGNORE},
        data={CONF_UNIQUE_ID: HOSTNAME},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf discovery."""
    assert not hass.data.get(DOMAIN)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="VELUX_KLF_LAN_ABCD",
            port="",
            type="",
            name="VELUX_KLF_LAN_ABCD",
            properties="",
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_zeroconf_discovery_abort(hass: HomeAssistant) -> None:
    """Test a wrong ZeroconfServiceInfo."""
    # Setup entry.
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id is None
    await hass.async_block_till_done()

    # Set unique_id for already configured entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(HOST),
            ip_addresses=[ip_address(HOST)],
            hostname=HOSTNAME,
            port="",
            type="",
            name="VELUX_KLF_LAN_ABCD",
            properties="",
        ),
    )
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == HOSTNAME
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert result["type"] == FlowResultType.ABORT


async def test_zeroconf_discovery_new_ip(hass: HomeAssistant) -> None:
    """Test a wrong ZeroconfServiceInfo."""
    # Setup entry.
    with patch(PYVLX_CONFIG_FLOW_CLASS_PATH, autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=DUMMY_DATA,
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PASSWORD: PASSWORD,
    }
    pyvlx.assert_called_once_with(host=HOST, password=PASSWORD)
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == HOST

    # Set unique_id from zeroconf.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address(HOST),
            ip_addresses=[ip_address(HOST)],
            hostname=HOSTNAME,
            port="",
            type="",
            name="VELUX_KLF_LAN_ABCD",
            properties="",
        ),
    )
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == HOSTNAME
    assert result["type"] == FlowResultType.ABORT

    # Update ip address of already configured unique_id.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.1.1.2"),
            ip_addresses=[ip_address("127.1.1.2")],
            hostname="VELUX_KLF_LAN_ABCD",
            port="",
            type="",
            name="VELUX_KLF_LAN_ABCD",
            properties="",
        ),
    )
    assert hass.config_entries.async_entries(DOMAIN)[0].data[CONF_HOST] == "127.1.1.2"
    assert result["type"] == FlowResultType.ABORT
