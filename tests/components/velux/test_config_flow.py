"""Tests for the Velux config flow."""
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from pyvlx import PyVLX, PyVLXException

from homeassistant.components import zeroconf
from homeassistant.components.velux.const import DOMAIN
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_UNIGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TestPyVLX
from .const import HOST, HOSTNAME, PASSWORD


@patch("homeassistant.components.velux.config_flow.PyVLX", new=AsyncMock, spec=PyVLX)
async def test_async_step_import(hass: HomeAssistant) -> None:
    """Test import step."""
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: HOST,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_PASSWORD: PASSWORD,
    }
    pyvlx.assert_called_once_with(host=HOST, password=PASSWORD)


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


@patch.object(
    PyVLX,
    "connect",
    new=AsyncMock(side_effect=OSError),
    spec=PyVLX,
)
async def test_async_step_wrong_host(hass: HomeAssistant) -> None:
    """Test import user."""
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: "wrong",
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"]["base"] == "invalid_host"
    pyvlx.assert_not_called()


@patch.object(
    PyVLX,
    "connect",
    new=AsyncMock(side_effect=PyVLXException("wrong_password")),
    spec=PyVLX,
)
async def test_async_step_wrong_password(hass: HomeAssistant) -> None:
    """Test import user."""
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_PASSWORD: "wrong",
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"]["base"] == "invalid_auth"
    pyvlx.assert_not_called()


@patch.object(PyVLX, "connect", new=AsyncMock(side_effect=ConnectionAbortedError))
async def test_async_step_fails(hass: HomeAssistant) -> None:
    """Test import user."""
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"]["base"] == "cannot_connect"
    pyvlx.assert_not_called()


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
            hostname=HOSTNAME,
            port="",
            type="",
            name="VELUX_KLF_LAN_ABCD",
            properties="",
        ),
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


@patch("homeassistant.components.velux.config_flow.PyVLX", new=TestPyVLX)
@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_zeroconf_discovery_abort(hass: HomeAssistant) -> None:
    """Test a wrong ZeroconfServiceInfo."""
    # Setup entry.
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: HOST,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id is None
    hass.async_block_till_done()

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


@patch("homeassistant.components.velux.config_flow.PyVLX", new=TestPyVLX)
@patch("homeassistant.components.velux.PyVLX", new=TestPyVLX)
async def test_zeroconf_discovery_new_ip(hass: HomeAssistant) -> None:
    """Test a wrong ZeroconfServiceInfo."""
    # Setup entry .
    with patch("homeassistant.components.velux.PyVLX", autospec=True) as pyvlx:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: HOST,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert hass.data.get(DOMAIN)
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
