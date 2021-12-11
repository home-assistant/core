"""Tests for the Legrand RFLC component."""
from typing import Final
from unittest.mock import patch

import lc7001.aio

from homeassistant import data_entry_flow
from homeassistant.components.legrand_rflc.config_flow import ConfigFlow

from .emulation import Server

COMPOSER: Final = lc7001.aio.Composer()


async def test_security_setkey(hass):
    """Test security compliant LC7001 in [SETKEY] mode (factory reset)."""
    sessions = [
        [
            b'[SETKEY]\x00{"MAC":"0026EC000000"}',
            COMPOSER.wrap(
                1,
                COMPOSER.compose_keys(
                    bytes.fromhex(Server.AUTHENTICATION_OLD),
                    bytes.fromhex(Server.AUTHENTICATION),
                ),
            ),
            b'{"ID":1,"Service":"SetSystemProperties","Status":"Success","ErrorCode":0}\x00',
            COMPOSER.wrap(2, COMPOSER.compose_list_zones()),
            b'{"ID":2,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
        ],
    ]
    await Server(hass, sessions).start()


async def test_security_hello(hass):
    """Test security compliant LC7001 "Hello" challenge."""
    sessions = [
        Server.SECURITY_HELLO_AUTHENTICATION_OK
        + [
            COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
            b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
        ],
    ]
    await Server(hass, sessions).start()


async def test_security_non_compliant(hass):
    """Test security non-compliant LC7001 (no authentication)."""
    sessions = [
        [
            Server.SECURITY_NON_COMPLIANT,
            COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
            b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
        ],
    ]
    await Server(hass, sessions).start()


async def test_security_hello_reload(hass):
    """Test security compliant LC7001 "Hello" challenge with reload."""
    sessions = [
        Server.SECURITY_HELLO_AUTHENTICATION_OK
        + [
            COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
            b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00{"ID":0,"Service":"ZoneAdded","ZID":0,"Status":"Success"}\x00',
        ],
        Server.SECURITY_HELLO_AUTHENTICATION_OK
        + [
            COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
            b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
        ],
    ]
    await Server(hass, sessions).start()


async def _reauth_confirm(self: ConfigFlow, user_input) -> data_entry_flow.FlowResult:
    return await self.async_step_reauth_confirm(user_input)


async def test_security_hello_reauth(hass):
    """Test security compliant LC7001 "Hello" challenge with reauth."""
    with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
        sessions = [
            Server.SECURITY_HELLO_AUTHENTICATION_INVALID,
            Server.SECURITY_HELLO_AUTHENTICATION_OK,
            Server.SECURITY_HELLO_AUTHENTICATION_OK
            + [
                COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
                b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
            ],
        ]
        await Server(hass, sessions).start()


async def test_security_hello_reauth_invalid_mac(hass):
    """Test security compliant LC7001 "Hello" challenge with reauth for invalid mac."""
    with patch.object(ConfigFlow, "async_step_reauth", _reauth_confirm):
        sessions = [
            Server.SECURITY_HELLO_AUTHENTICATION_INVALID_MAC,
            Server.SECURITY_HELLO_AUTHENTICATION_OK,
            Server.SECURITY_HELLO_AUTHENTICATION_OK
            + [
                COMPOSER.wrap(1, COMPOSER.compose_list_zones()),
                b'{"ID":1,"Service":"ListZones","ZoneList":[],"Status":"Success"}\x00',
            ],
        ]
        await Server(hass, sessions).start()
