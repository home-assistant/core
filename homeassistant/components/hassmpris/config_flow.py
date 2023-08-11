"""Config flow for MPRIS media playback remote control integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import hassmpris_client
import pskca
from shortauthstrings import emoji
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .cert_data import Certificate, CertStore, PrivateKeyTypes
from .const import (
    CONF_CAKES_PORT,
    CONF_HOST,
    CONF_MPRIS_PORT,
    CONF_UNIQUE_ID,
    DEF_CAKES_PORT,
    DEF_HOST,
    DEF_MPRIS_PORT,
    DOMAIN,
    LOGGER as _LOGGER,
    REASON_CANNOT_CONNECT,
    REASON_CANNOT_DECRYPT,
    REASON_IGNORED,
    REASON_INVALID_ZEROCONF,
    REASON_REJECTED,
    REASON_TIMEOUT,
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
    return f"{host}:{cakes_port}:{mpris_port}"


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
        self._title: str | None = None
        self._unique_id: str | None = None
        self._cakes_port: int = DEF_CAKES_PORT
        self._mpris_port: int = DEF_MPRIS_PORT
        self._client_cert: Certificate | None = None
        self._client_key: PrivateKeyTypes | None = None
        self._trust_chain: list[Certificate] | None = None
        self._cakes_client: hassmpris_client.AsyncCAKESClient | None = None

    @callback
    def _get_data(self):
        data = {
            CONF_UNIQUE_ID: self._unique_id,
            CONF_HOST: self._host,
            CONF_CAKES_PORT: self._cakes_port,
            CONF_MPRIS_PORT: self._mpris_port,
        }
        return data

    @callback
    def _get_cert_data(
        self,
    ) -> tuple[Certificate, PrivateKeyTypes, list[Certificate]]:
        assert self._client_cert is not None
        assert self._client_key is not None
        assert self._trust_chain is not None
        return self._client_cert, self._client_key, self._trust_chain

    def _set_data(
        self,
        title: str | None,
        host: str,
        cakes_port: int,
        mpris_port: int,
        unique_id: str | None = None,
    ):
        self._title = title
        self._host = host
        self._cakes_port = cakes_port
        self._mpris_port = mpris_port
        self._unique_id = unique_id

    def _get_unique_id_by_connection_data(self):
        return _genuid(self._host, self._cakes_port, self._mpris_port)

    def _get_unique_id_by_zeroconf(self):
        return self._unique_id

    def _get_any_unique_id(self):
        if id_ := self._get_unique_id_by_zeroconf():
            return id_
        return self._get_unique_id_by_connection_data()

    def _update_server_data(self, host: str, cakes_port: int, mpris_port: int):
        self._host = host
        self._cakes_port = cakes_port
        self._mpris_port = mpris_port

    async def _create_entry(self):
        async def persist_cert_data(unique_id: str):
            """Persist the certificate data just generated in this flow."""
            await CertStore(
                self.hass,
                unique_id,
            ).save_cert_data(*self._get_cert_data())

        data = self._get_data()

        # Update existing entry that has the same unique ID.
        if zeroconf_uid := self._get_unique_id_by_zeroconf():
            if existing_entry := await self.async_set_unique_id(zeroconf_uid):
                _LOGGER.debug("Existing entry, unique ID: %s", existing_entry.unique_id)
                await persist_cert_data(existing_entry.unique_id)
                self.hass.config_entries.async_update_entry(existing_entry, data=data)
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        # Update existing entry that has the same host / ports.
        if existing_entry := await self.async_set_unique_id(
            self._get_unique_id_by_connection_data()
        ):
            _LOGGER.debug("Existing entry, generated ID: %s", existing_entry.unique_id)
            await persist_cert_data(existing_entry.unique_id)
            self.hass.config_entries.async_update_entry(existing_entry, data=data)
            await self.hass.config_entries.async_reload(existing_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        # OK, no entries found with those two identifiers.
        # Let's set a unique ID.
        await self.async_set_unique_id(self._get_any_unique_id())
        _LOGGER.debug("New entry")
        assert self._title, "Impossible: the title is %r" % self._title
        await persist_cert_data(self._get_any_unique_id())
        return self.async_create_entry(
            title=self._title,
            data=data,
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

        self._set_data(
            f"MPRIS on {user_input[CONF_HOST]}",
            user_input[CONF_HOST],
            user_input[CONF_CAKES_PORT],
            user_input[CONF_MPRIS_PORT],
        )

        # Do not proceed if the device is already configured by hand.
        await self.async_set_unique_id(self._get_unique_id_by_connection_data())
        self._abort_if_unique_id_configured()

        return await self.async_step_pairing()

    async def async_step_zeroconf(
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle zeroconf discovery."""
        try:
            assert discovery_info.host
            assert discovery_info.port
            assert discovery_info.hostname
            assert discovery_info.name
            assert discovery_info.properties
            assert CONF_CAKES_PORT in discovery_info.properties
        except AssertionError:
            _LOGGER.debug("Ignoring invalid zeroconf announcement: %s", discovery_info)
            return self.async_abort(reason=REASON_INVALID_ZEROCONF)

        self._set_data(
            discovery_info.name.split(".")[0],
            discovery_info.host,
            int(discovery_info.properties[CONF_CAKES_PORT]),
            int(discovery_info.port or DEF_MPRIS_PORT),
            discovery_info.hostname,
        )

        # # Do not proceed if the device is already configured by hand.
        await self.async_set_unique_id(self._get_unique_id_by_connection_data())
        self._abort_if_unique_id_configured()

        # Do not proceed if the device is already configured by Zeroconf.
        await self.async_set_unique_id(self._get_unique_id_by_zeroconf())
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

        self._update_server_data(
            user_input[CONF_HOST],
            user_input[CONF_CAKES_PORT],
            user_input[CONF_MPRIS_PORT],
        )

        return await self.async_step_pairing()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle the reauth step."""
        assert entry_data, "Impossible entry data empty"
        self._set_data(
            None,
            entry_data[CONF_HOST],
            entry_data[CONF_CAKES_PORT],
            entry_data[CONF_MPRIS_PORT],
            entry_data[CONF_UNIQUE_ID],
        )
        await self.async_set_unique_id(self._get_any_unique_id())
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> FlowResult:
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

        self._update_server_data(
            user_input[CONF_HOST],
            user_input[CONF_CAKES_PORT],
            user_input[CONF_MPRIS_PORT],
        )

        return await self.async_step_pairing()

    async def async_step_pairing(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the pairing step of auth."""
        assert self._client_cert is None
        (
            csr,
            self._client_key,
        ) = pskca.create_certificate_signing_request()
        self._cakes_client = hassmpris_client.AsyncCAKESClient(
            self._host,
            self._cakes_port,
            csr,
        )
        try:
            ecdh = await self._cakes_client.obtain_verifier()
        except hassmpris_client.Timeout:
            return self.async_abort(reason=REASON_TIMEOUT)
        except hassmpris_client.ClientException:
            return self.async_abort(reason=REASON_CANNOT_CONNECT)
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
            last_step=True,
        )

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the confirmation that pairing went well."""
        assert self._cakes_client
        try:
            (
                self._client_cert,
                self._trust_chain,
            ) = await self._cakes_client.obtain_certificate()
        except hassmpris_client.Ignored:
            return self.async_abort(reason=REASON_IGNORED)
        except hassmpris_client.Rejected:
            return self.async_abort(reason=REASON_REJECTED)
        except hassmpris_client.CannotDecrypt:
            return self.async_abort(reason=REASON_CANNOT_DECRYPT)
        except hassmpris_client.Timeout:
            return self.async_abort(reason=REASON_TIMEOUT)
        except hassmpris_client.CannotConnect:
            return self.async_abort(reason=REASON_CANNOT_CONNECT)
        except hassmpris_client.ClientException:
            return self.async_abort(reason=REASON_CANNOT_CONNECT)

        return await self._create_entry()
