"""Tests for the Legrand RFLC component configuration flows."""

import logging
from typing import Final
from unittest.mock import PropertyMock, patch

import lc7001.aio

from homeassistant import setup
from homeassistant.components.dhcp import IP_ADDRESS
from homeassistant.components.legrand_rflc.config_flow import ConfigFlow
from homeassistant.components.legrand_rflc.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .emulation import Server

from tests.common import MockConfigEntry

_LOGGER: Final = logging.getLogger(__name__)

COMPOSER: Final = lc7001.aio.Composer()

HOST: Final = Server.HOST
ADDRESS: Final = Server.ADDRESS
INVALID_HOST: Final = "name.invalid."
INVALID_ADDRESS: Final = "0.0.0.0"

PATCH_HOST: Final = patch(
    "homeassistant.components.legrand_rflc.config_flow.ConfigFlow.HOST",
    new_callable=PropertyMock,
)


async def test_step_dhcp_form(hass):
    """Test successful dhcp step in configuration flow."""
    with PATCH_HOST as mock:
        mock.return_value = HOST
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data={IP_ADDRESS: ADDRESS}
        )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_dhcp_invalid_host(hass):
    """Test invalid host dhcp step in configuration flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with PATCH_HOST as mock:
        mock.return_value = INVALID_HOST
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_DHCP}, data={IP_ADDRESS: ADDRESS}
        )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == ConfigFlow.ABORT_NO_DEVICES_FOUND


async def test_step_dhcp_invalid_address(hass):
    """Test invalid address dhcp step in configuration flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with PATCH_HOST as mock:
        mock.return_value = HOST
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data={IP_ADDRESS: INVALID_ADDRESS},
        )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == ConfigFlow.ABORT_NO_DEVICES_FOUND


async def test_step_user(hass):
    """Test user step in configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM


async def test_step_user_invalid_host(hass):
    """Test invalid host user step in configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: INVALID_HOST},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_step_user_invalid_auth(hass):
    """Test invalid auth user step in configuration flow."""
    sessions = [
        [
            b"Hello V1 \x009158E315149BEF9F2179D79C58F0F422 0026EC000000",
            b"3437872f1912fe9fb06ddf50eb5bf535",
            b"[INVALID]\x00",
        ],
    ]
    server_port = await Server(hass, sessions).start(False)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: Server.HOST,
            CONF_PORT: server_port,
            CONF_PASSWORD: Server.PASSWORD,
        },
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}
    await hass.async_block_till_done()


async def test_step_user_create_entry(hass):
    """Test create entry user step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_OK]
    server_port = await Server(hass, sessions).start(False)
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.legrand_rflc.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: Server.HOST,
                CONF_PORT: server_port,
                CONF_PASSWORD: Server.PASSWORD,
            },
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()


async def test_step_reauth(hass):
    """Test reauth step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_OK]
    server_port = await Server(hass, sessions).start(False)
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.legrand_rflc.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry": entry,
                "unique_id": Server.HOST,
            },
            data={
                CONF_HOST: Server.HOST,
                CONF_PORT: server_port,
                CONF_PASSWORD: Server.PASSWORD,
            },
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == ConfigFlow.ABORT_REAUTH_SUCCESSFUL
        await hass.async_block_till_done()


async def test_step_reauth_invalid_authentication(hass):
    """Test invalid authentication reauth step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_INVALID]
    server_port = await Server(hass, sessions).start(False)
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": Server.HOST,
        },
        data={
            CONF_HOST: Server.HOST,
            CONF_PORT: server_port,
            CONF_PASSWORD: Server.PASSWORD,
        },
    )
    assert result["type"] == RESULT_TYPE_FORM
    await hass.async_block_till_done()


async def test_step_reauth_invalid_host(hass):
    """Test invalid host reauth step in configuration flow."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": INVALID_HOST,
        },
        data={
            CONF_HOST: INVALID_HOST,
        },
    )
    assert result["type"] == RESULT_TYPE_FORM
