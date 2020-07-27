"""Tests for ComfoAir config flow."""

import asyncio
import socket

import serial.tools.list_ports

from homeassistant import setup
from homeassistant.components.comfoair import config_flow
from homeassistant.components.comfoair.const import (
    CONF_SERIAL_PORT,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


class ComfoAirSim(asyncio.Protocol):
    """Mock of a silent ComfoAir device."""


def com_port(device):
    """Mock of a serial port."""
    port = serial.tools.list_ports_common.ListPortInfo()
    port.serial_number = "1234"
    port.manufacturer = "Virtual serial port"
    port.device = device
    port.description = "Some serial port"

    return port


def first_host_and_port(srv):
    """Return first host and port of a server."""

    for sock in srv.sockets:
        if sock.family == socket.AF_INET:
            return sock.getsockname()
        if sock.family == socket.AF_INET6:
            return sock.getsockname()[0:2]

    raise ValueError("Invalid socket")


async def simulator():
    """Return server and URL."""
    loop = asyncio.get_running_loop()
    srv = await loop.create_server(ComfoAirSim, port=0)
    host, port = first_host_and_port(srv)
    return srv, f"socket://{host}:{port}"


async def test_user_flow(hass):
    """Test user flow."""
    srv, url = await simulator()
    async with srv:
        with patch(
            "serial.tools.list_ports.comports", MagicMock(return_value=[com_port(url)])
        ):
            port = com_port(url)
            port_select = f"{port}, s/n: {port.serial_number} - {port.manufacturer}"

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={CONF_SOURCE: SOURCE_USER},
                data={CONF_NAME: DEFAULT_NAME, CONF_SERIAL_PORT: port_select},
            )
            assert result["type"] == RESULT_TYPE_CREATE_ENTRY
            assert result["title"].startswith(port.description)
            assert result["data"] == {
                CONF_NAME: DEFAULT_NAME,
                CONF_SERIAL_PORT: port.device,
            }


async def test_user_flow_show_form(hass):
    """Test user step form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_user_flow_manual(hass):
    """Test user flow manual entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_SERIAL_PORT: config_flow.CONF_MANUAL_PATH},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "port_config"


async def test_user_flow_existing_config_entry(hass):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, data={CONF_SERIAL_PORT: "/dev/ttyUSB1"}).add_to_hass(
        hass
    )
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    assert result["type"] == "abort"


async def test_user_port_config(hass):
    """Test port config."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_NAME: DEFAULT_NAME, CONF_SERIAL_PORT: config_flow.CONF_MANUAL_PATH},
    )

    srv, url = await simulator()
    async with srv:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_NAME: DEFAULT_NAME, CONF_SERIAL_PORT: url},
        )

        assert result["type"] == "create_entry"
        assert result["title"].startswith(url)
        assert result["data"] == {
            CONF_NAME: DEFAULT_NAME,
            CONF_SERIAL_PORT: url,
        }
