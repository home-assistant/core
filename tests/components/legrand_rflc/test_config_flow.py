"""Tests for the Legrand RFLC component configuration flows."""

from typing import Final
from unittest.mock import PropertyMock, patch

import lc7001.aio

from homeassistant import data_entry_flow
from homeassistant.components.dhcp import IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.legrand_rflc.config_flow import ConfigFlow
from homeassistant.components.legrand_rflc.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .emulation import Server

from tests.common import MockConfigEntry

COMPOSER: Final = lc7001.aio.Composer()

HOST: Final = Server.HOST
ADDRESS: Final = Server.ADDRESS
MAC: Final = Server.MAC
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
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data={IP_ADDRESS: ADDRESS, MAC_ADDRESS: MAC},
        )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_dhcp_invalid_host(hass):
    """Test invalid host dhcp step in configuration flow."""
    with PATCH_HOST as mock:
        mock.return_value = INVALID_HOST
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data={IP_ADDRESS: ADDRESS, MAC_ADDRESS: MAC},
        )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == ConfigFlow.ABORT_NO_DEVICES_FOUND


async def test_step_dhcp_invalid_address(hass):
    """Test invalid address dhcp step in configuration flow."""
    with PATCH_HOST as mock:
        mock.return_value = HOST
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data={IP_ADDRESS: INVALID_ADDRESS, MAC_ADDRESS: MAC},
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
    async with Server.Context(Server(hass, sessions)):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: Server.HOST,
                CONF_PASSWORD: Server.PASSWORD,
            },
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_step_user_create_entry(hass):
    """Test create entry user step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_OK]
    async with Server.Context(Server(hass, sessions)):
        with patch(
            "homeassistant.components.legrand_rflc.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_USER},
                data={
                    CONF_HOST: Server.HOST,
                    CONF_PASSWORD: Server.PASSWORD,
                },
            )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY


async def _reauth_confirm(self: ConfigFlow, user_input) -> data_entry_flow.FlowResult:
    self._data = user_input
    return await self.async_step_reauth_confirm(user_input)


async def test_step_reauth(hass):
    """Test reauth step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_OK]
    async with Server.Context(Server(hass, sessions)):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)
        with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
            with patch(
                "homeassistant.components.legrand_rflc.async_setup_entry",
                return_value=True,
            ):
                result = await hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={
                        "source": SOURCE_REAUTH,
                        "entry_id": entry.entry_id,
                        "unique_id": Server.MAC.lower(),
                    },
                    data={
                        CONF_HOST: Server.HOST,
                        CONF_PASSWORD: Server.PASSWORD,
                    },
                )
                assert result["type"] == RESULT_TYPE_ABORT
                assert result["reason"] == ConfigFlow.ABORT_REAUTH_SUCCESSFUL


async def test_step_reauth_invalid_authentication(hass):
    """Test invalid authentication reauth step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_INVALID]
    async with Server.Context(Server(hass, sessions)):
        with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_REAUTH,
                    "unique_id": Server.MAC.lower(),
                },
                data={
                    CONF_HOST: Server.HOST,
                    CONF_PASSWORD: Server.PASSWORD,
                },
            )
            assert result["type"] == RESULT_TYPE_FORM


async def test_step_reauth_invalid_host(hass):
    """Test invalid host reauth step in configuration flow."""
    with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
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


async def test_step_reauth_invalid_host_mac(hass):
    """Test invalid host mac reauth step in configuration flow."""
    sessions = [Server.SECURITY_HELLO_AUTHENTICATION_OK]
    async with Server.Context(Server(hass, sessions)):
        with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": SOURCE_REAUTH,
                    "unique_id": Server.MAC.upper(),
                },
                data={
                    CONF_HOST: Server.HOST,
                    CONF_PASSWORD: Server.PASSWORD,
                },
            )
            assert result["type"] == RESULT_TYPE_FORM
