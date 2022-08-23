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
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_TRUST_CHAIN,
    DOMAIN,
    STEP_CONFIRM,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host", description={"suggested_value": "localhost"}): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MPRIS media playback remote control."""

    VERSION = 1

    def __init__(self):
        """Initialize flow."""
        self._count = 0
        self._host: str | None = None
        self._client_cert: str | None = None
        self._client_key: str | None = None
        self._trust_chain: str | None = None
        self._confirmed: asyncio.Future[bool] | None = None
        self._cakes_client: hassmpris_client.AsyncCAKESClient | None = None

    @callback
    def _get_data(self):
        data = {
            "name": self._host,
            "host": self._host,
            CONF_CLIENT_CERT: self._client_cert if self._client_cert else None,
            CONF_CLIENT_KEY: self._client_key if self._client_key else None,
            CONF_TRUST_CHAIN: self._trust_chain if self._trust_chain else None,
        }
        return data

    async def _create_entry(self):
        data = self._get_data()
        existing_entry = await self.async_set_unique_id(self._host)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self._host,
            data=self._get_data(),
        )

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        host = discovery_info.host
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()
        self._host = host
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the Zeroconf confirmation step."""
        if not user_input:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "host", description={"suggested_value": self._host}
                        ): str,
                    }
                ),
                errors={},
            )
        self._host = user_input["host"]
        # Do not proceed if the device is already configured.
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()
        return await self.async_step_pairing()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={},
            )

        self._host = user_input["host"]
        # Do not proceed if the device is already configured.
        await self.async_set_unique_id(self._host)
        self._abort_if_unique_id_configured()
        return await self.async_step_pairing()

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        """Handle the reauth step."""
        assert user_input, "not possible"
        self._host = user_input["host"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle the confirmation of reauth."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
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
            40052,
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
