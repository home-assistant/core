"""Config flow for MPRIS media playback remote control integration."""
from __future__ import annotations

import asyncio
from typing import Any

from cryptography.hazmat.primitives import serialization
import hassmpris_client
import pskca
from shortauthstrings import emoji
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_CAKES_PORT,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_HOST,
    CONF_MPRIS_PORT,
    CONF_TRUST_CHAIN,
    CONF_UNIQUE_ID,
    DEF_CAKES_PORT,
    DEF_HOST,
    DEF_MPRIS_PORT,
    DOMAIN,
    LOGGER as _LOGGER,
    STEP_CONFIRM,
    STEP_REAUTH_CONFIRM,
    STEP_USER,
    STEP_ZEROCONF_CONFIRM,
)


def _conf_schema_factory(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST,
                description={
                    "suggested_value": defaults.get(
                        CONF_HOST,
                        DEF_HOST,
                    ),
                },
            ): vol.All(str, vol.Length(min=4)),
            vol.Required(
                CONF_CAKES_PORT,
                description={
                    "suggested_value": defaults.get(
                        CONF_CAKES_PORT,
                        DEF_CAKES_PORT,
                    ),
                },
            ): vol.All(int, vol.Range(min=1025, max=65535)),
            vol.Required(
                CONF_MPRIS_PORT,
                description={
                    "suggested_value": defaults.get(
                        CONF_MPRIS_PORT,
                        DEF_MPRIS_PORT,
                    ),
                },
            ): vol.All(int, vol.Range(min=1025, max=65535)),
        }
    )


def _genuid(host, cakes_port, mpris_port):
    return "{}:{}:{}".format(
        host,
        cakes_port,
        mpris_port,
    )


def _preconfigured_schema(host: str, cakes_port: int, mpris_port: int) -> vol.Schema:
    return _conf_schema_factory(
        {
            CONF_HOST: host,
            CONF_CAKES_PORT: cakes_port,
            CONF_MPRIS_PORT: mpris_port,
        }
    )


STEP_USER_DATA_SCHEMA = _conf_schema_factory({})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MPRIS media playback remote control."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._count = 0
        self._host: str = DEF_HOST
        self._title: str = DEF_HOST
        self._unique_id: str | None = None
        self._cakes_port: int = DEF_CAKES_PORT
        self._mpris_port: int = DEF_MPRIS_PORT
        self._client_cert: str | None = None
        self._client_key: str | None = None
        self._trust_chain: str | None = None
        self._confirmed: asyncio.Future[bool] | None = None
        self._cakes_client: hassmpris_client.AsyncCAKESClient | None = None

    @callback
    def _get_data(self):
        data = {
            CONF_UNIQUE_ID: self._unique_id,
            CONF_HOST: self._host,
            CONF_CAKES_PORT: self._cakes_port,
            CONF_MPRIS_PORT: self._mpris_port,
            CONF_CLIENT_CERT: self._client_cert if self._client_cert else None,
            CONF_CLIENT_KEY: self._client_key if self._client_key else None,
            CONF_TRUST_CHAIN: self._trust_chain if self._trust_chain else None,
        }
        return data

    async def _create_entry(self):
        data = self._get_data()

        # Update existing entry that has the same unique ID.
        if self._unique_id:
            existing_entry = await self.async_set_unique_id(self._unique_id)
            if existing_entry:
                self.hass.config_entries.async_update_entry(existing_entry, data=data)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # Update existing entry that has the same host / ports.
        existing_entry = await self.async_set_unique_id(
            _genuid(self._host, self._cakes_port, self._mpris_port)
        )
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self._title,
            data=self._get_data(),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id=STEP_USER,
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={},
            )

        self._host = user_input[CONF_HOST]
        self._cakes_port = user_input[CONF_CAKES_PORT]
        self._mpris_port = user_input[CONF_MPRIS_PORT]
        self._title = f"MPRIS on {self._host}"

        # Do not proceed if the device is already configured by hand.
        await self.async_set_unique_id(
            _genuid(
                self._host,
                self._cakes_port,
                self._mpris_port,
            )
        )
        self._abort_if_unique_id_configured()

        return await self.async_step_pairing()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        # Sample:
        # ZeroconfServiceInfo(
        #   host='10.250.4.12',
        #   addresses=['10.250.4.12', '127.0.0.1'],
        #   port=40051,
        #   hostname='hassmpris-f7ca73ec-ab9d-32b3-9c6d-e01a3b218451.local.',
        #   type='_hassmpris._tcp.local.',
        #   name='MPRIS on user@projects._hassmpris._tcp.local.',
        #   properties={'cakes_port': '40051'}
        # )

        try:
            assert discovery_info.host
            assert discovery_info.port
            assert discovery_info.hostname
            assert discovery_info.name
            assert discovery_info.properties
            assert CONF_CAKES_PORT in discovery_info.properties
        except AssertionError:
            _LOGGER.debug("Ignoring invalid zeroconf announcement: %s", discovery_info)

        self._unique_id = discovery_info.hostname
        self._host = discovery_info.host
        self._cakes_port = int(discovery_info.properties[CONF_CAKES_PORT])
        self._mpris_port = int(discovery_info.port or DEF_MPRIS_PORT)
        self._title = discovery_info.name.split(".")[0]

        # Do not proceed if the device is already configured by hand.
        await self.async_set_unique_id(
            _genuid(self._host, self._cakes_port, self._mpris_port)
        )
        self._abort_if_unique_id_configured()

        # Do not proceed if the device is already configured by Zeroconf.
        await self.async_set_unique_id(self._unique_id)
        self._abort_if_unique_id_configured()

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Zeroconf confirmation step."""
        if not user_input:
            return self.async_show_form(
                step_id=STEP_ZEROCONF_CONFIRM,
                data_schema=_preconfigured_schema(
                    self._host,
                    self._cakes_port,
                    self._mpris_port,
                ),
                errors={},
            )

        self._host = user_input[CONF_HOST]
        self._cakes_port = user_input[CONF_CAKES_PORT]
        self._mpris_port = user_input[CONF_MPRIS_PORT]

        # Do not proceed if the device is already configured by hand.
        await self.async_set_unique_id(
            _genuid(self._host, self._cakes_port, self._mpris_port)
        )
        self._abort_if_unique_id_configured()

        return await self.async_step_pairing()

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        """Handle the reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle the confirmation of reauth."""
        if not user_input:
            return self.async_show_form(
                step_id=STEP_REAUTH_CONFIRM,
                data_schema=_preconfigured_schema(
                    self._host,
                    self._cakes_port,
                    self._mpris_port,
                ),
            )

        if (
            self._host != user_input[CONF_HOST]
            or self._cakes_port != user_input[CONF_CAKES_PORT]
            or self._mpris_port != user_input[CONF_MPRIS_PORT]
        ):
            # User has changed the information shown to him.
            # This may be an altogether different server, so
            # we must check if it has been set up.
            self._host = user_input[CONF_HOST]
            self._cakes_port = user_input[CONF_CAKES_PORT]
            self._mpris_port = user_input[CONF_MPRIS_PORT]

            # Do not proceed if the device is already configured by hand.
            await self.async_set_unique_id(
                _genuid(self._host, self._cakes_port, self._mpris_port)
            )
            self._abort_if_unique_id_configured()

        self._client_cert = None
        return await self.async_step_pairing()

    async def async_step_pairing(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Handle the pairing step of auth."""
        assert not self._client_cert
        (
            csr,
            key,
        ) = pskca.create_certificate_signing_request()
        self._client_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        self._cakes_client = hassmpris_client.AsyncCAKESClient(
            self._host,
            self._cakes_port,
            csr,
        )
        try:
            ecdh = await self._cakes_client.obtain_verifier()
        except hassmpris_client.Timeout:
            return self.async_abort(reason="timeout_connect")
        except hassmpris_client.ClientException:
            return self.async_abort(reason="cannot_connect")
        emojis = emoji(ecdh.derived_key, 6)

        return self.async_show_form(
            step_id=STEP_CONFIRM,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "emojis", description={"suggested_value": emojis}
                    ): str,
                }
            ),
            errors={},
        )

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Handle the confirmation that pairing went well."""
        assert self._cakes_client
        try:
            (
                cert,
                trust_chain,
            ) = await self._cakes_client.obtain_certificate()
            self._client_cert = cert.public_bytes(serialization.Encoding.PEM).decode(
                "ascii"
            )
            self._trust_chain = "\n".join(
                x.public_bytes(serialization.Encoding.PEM).decode("ascii")
                for x in trust_chain
            )
        except hassmpris_client.Ignored:
            return self.async_abort(reason="ignored")
        except hassmpris_client.Rejected:
            return self.async_abort(reason="rejected")
        except hassmpris_client.CannotDecrypt:
            return self.async_abort(reason="cannot_decrypt")
        except hassmpris_client.Timeout:
            return self.async_abort(reason="timeout_connect")
        except hassmpris_client.CannotConnect:
            return self.async_abort(reason="cannot_connect")

        return await self._create_entry()
