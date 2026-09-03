"""Config flow for the Poolside integration."""

import asyncio
from base64 import b64decode, b64encode
from collections.abc import Mapping
import contextlib
from typing import Any, override

import aiohttp
from aiopoolside import (
    PairingApproved,
    PairingBusy,
    PairingError,
    PairingInvalid,
    PairingRejected,
    PairingTimedOut,
    PoolsideAuthError,
    PoolsideClient,
    PoolsideCommandError,
    PoolsideConnectionError,
    async_await_pairing_result,
    async_request_pairing,
    generate_keypair,
    public_key_from_private,
)
from aiopoolside.const import DEFAULT_PORT
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    CONF_CLIENT_NAME,
    CONF_CLIENT_PRIVATE_KEY,
    CONF_CONTROLLER_PUBLIC_KEY,
    CONF_CONTROLLER_UUID,
    CONF_EXPOSE_POOL_DEVICES,
    DEFAULT_EXPOSE_POOL_DEVICES,
    DOMAIN,
    ZEROCONF_PROP_NAME,
    ZEROCONF_PROP_UUID,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

INITIAL_PAIR_TIMEOUT = 10

_ABORT_REASONS: dict[type[Exception], str] = {
    PairingRejected: "pair_rejected",
    PairingTimedOut: "pair_timeout",
    PairingBusy: "pair_busy",
    PairingInvalid: "pair_failed",
}


class PoolsideOptionsFlow(OptionsFlowWithReload):
    """Handle the Poolside options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXPOSE_POOL_DEVICES,
                        default=self.config_entry.options.get(
                            CONF_EXPOSE_POOL_DEVICES, DEFAULT_EXPOSE_POOL_DEVICES
                        ),
                    ): bool,
                }
            ),
        )


class PoolsideConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Poolside."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> PoolsideOptionsFlow:
        """Create the options flow."""
        return PoolsideOptionsFlow()

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._client_name: str = ""
        self._private_key: bytes = b""
        self._public_key: bytes = b""
        self._pair_task: asyncio.Task[PairingApproved] | None = None
        self._fingerprint: str | None = None
        self._approved: PairingApproved | None = None
        self._discovered_name: str = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: collect host and port."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        self._host = user_input[CONF_HOST]
        self._port = user_input[CONF_PORT]
        self._client_name = self.hass.config.location_name
        self._private_key, self._public_key = generate_keypair()
        return await self.async_step_pair()

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via mDNS/DNS-SD."""
        controller_uuid = discovery_info.properties.get(ZEROCONF_PROP_UUID)
        if not controller_uuid:
            return self.async_abort(reason="cannot_connect")

        await self.async_set_unique_id(controller_uuid)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: discovery_info.host,
                CONF_PORT: discovery_info.port or DEFAULT_PORT,
            }
        )

        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._discovered_name = (
            discovery_info.properties.get(ZEROCONF_PROP_NAME) or self._host
        )
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered controller before starting pairing."""
        if user_input is None:
            return self.async_show_form(
                step_id="zeroconf_confirm",
                description_placeholders={
                    "name": self._discovered_name,
                    "host": self._host,
                },
            )

        self._client_name = self.hass.config.location_name
        self._private_key, self._public_key = generate_keypair()
        return await self.async_step_pair()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth triggered by a revoked or unrecognized client key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth and re-run pairing with the existing client keypair."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        reauth_entry = self._get_reauth_entry()
        self._host = reauth_entry.data[CONF_HOST]
        self._port = reauth_entry.data[CONF_PORT]
        self._client_name = reauth_entry.data[CONF_CLIENT_NAME]
        self._private_key = b64decode(reauth_entry.data[CONF_CLIENT_PRIVATE_KEY])
        self._public_key = public_key_from_private(self._private_key)
        return await self.async_step_pair()

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Send the pairing request, then wait for the user to approve it."""
        if self._pair_task is None:
            try:
                async with asyncio.timeout(INITIAL_PAIR_TIMEOUT):
                    session = aiohttp_client.async_get_clientsession(self.hass)
                    ws, result = await async_request_pairing(
                        session,
                        self._host,
                        self._port,
                        self._client_name,
                        self._public_key,
                    )
            except (
                PairingRejected,
                PairingTimedOut,
                PairingBusy,
                PairingInvalid,
            ) as err:
                return self.async_abort(reason=_ABORT_REASONS[type(err)])
            except TimeoutError, aiohttp.ClientError, PairingError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors={"base": "cannot_connect"},
                )

            if isinstance(result, PairingApproved):
                self._approved = result
                return await self.async_step_finish()

            self._fingerprint = result.fingerprint
            self._pair_task = self.hass.async_create_task(
                async_await_pairing_result(ws), eager_start=False
            )

        if not self._pair_task.done():
            return self.async_show_progress(
                step_id="pair",
                progress_action="pair",
                description_placeholders={"fingerprint": self._fingerprint or ""},
                progress_task=self._pair_task,
            )

        try:
            self._approved = await self._pair_task
        except (
            PairingRejected,
            PairingTimedOut,
            PairingBusy,
            PairingInvalid,
        ) as err:
            return self.async_show_progress_done(next_step_id=_ABORT_REASONS[type(err)])
        except PairingError:
            return self.async_show_progress_done(next_step_id="pair_failed")
        finally:
            self._pair_task = None

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_pair_rejected(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The user rejected the pairing request on the controller."""
        return self.async_abort(reason="pair_rejected")

    async def async_step_pair_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nobody approved the request before the pairing window expired."""
        return self.async_abort(reason="pair_timeout")

    async def async_step_pair_busy(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Another pairing is already pending on the controller."""
        return self.async_abort(reason="pair_busy")

    async def async_step_pair_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The controller rejected the pairing request."""
        return self.async_abort(reason="pair_failed")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the session handshake works, then create or update the entry."""
        assert self._approved is not None
        approved = self._approved

        await self.async_set_unique_id(approved.controller_uuid)
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()

        client = PoolsideClient(
            session=aiohttp_client.async_get_clientsession(self.hass),
            host=self._host,
            port=self._port,
            client_private_key=self._private_key,
            controller_public_key=approved.controller_public_key,
            controller_uuid=approved.controller_uuid,
        )
        site_name = "Poolside"
        try:
            await client.async_connect()
            with contextlib.suppress(PoolsideConnectionError, PoolsideCommandError):
                site, _controls = await client.async_get_control_layout()
                site_name = site.name
        except PoolsideAuthError, PoolsideConnectionError:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )
        finally:
            await client.async_disconnect()

        data = {
            CONF_HOST: self._host,
            CONF_PORT: self._port,
            CONF_CLIENT_NAME: self._client_name,
            CONF_CLIENT_PRIVATE_KEY: b64encode(self._private_key).decode(),
            CONF_CONTROLLER_PUBLIC_KEY: b64encode(
                approved.controller_public_key
            ).decode(),
            CONF_CONTROLLER_UUID: approved.controller_uuid,
        }

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        return self.async_create_entry(title=site_name, data=data)
