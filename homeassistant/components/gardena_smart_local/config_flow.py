"""Config flow for GARDENA smart local."""

import base64
import logging
from typing import override

import aiohttp
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.ssl import get_default_no_verify_context

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import GardenaSmartLocalCoordinator

_LOGGER = logging.getLogger(__name__)


class GardenaSmartLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GARDENA smart local."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {"device": GardenaInclusionSubentryFlow}

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_port: int = DEFAULT_PORT

    @override
    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # A zeroconf-discovered entry for the same host would have a
            # different (mDNS name based) unique_id, so also match on host.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            # No stable identifier is known before connecting to the gateway.
            # pylint: disable-next=home-assistant-unique-id-ip-based
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            error = await _async_try_connect(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input[CONF_PASSWORD],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        name = discovery_info.hostname.removesuffix(".local.")
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT

        # A manually-added entry for the same host would have a different
        # (host based) unique_id, so also match on host.
        self._async_abort_entries_match({CONF_HOST: host})
        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured()

        self._discovered_host = host
        self._discovered_port = port
        self.context["title_placeholders"] = {"name": name, "host": host}

        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a zeroconf-discovered gateway."""
        errors: dict[str, str] = {}

        if user_input is not None:
            error = await _async_try_connect(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD, ""),
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=self.context["title_placeholders"]["name"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._discovered_host): str,
                    vol.Optional(CONF_PORT, default=self._discovered_port): int,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            description_placeholders={
                "name": self.context["title_placeholders"]["name"],
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            error = await _async_try_connect(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD, ""),
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST, "")): str,
                    vol.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                    vol.Optional(
                        CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
        )


async def _async_try_connect(host: str, port: int, password: str) -> str | None:
    """Try connecting to the gateway, returning an error string on failure."""
    ssl_context = get_default_no_verify_context()

    auth_b64 = base64.b64encode(f"_:{password}".encode()).decode("ascii")

    try:
        async with (
            aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session,
            session.ws_connect(
                URL.build(scheme="wss", host=host, port=port),
                ssl=ssl_context,
                headers={"Authorization": f"Basic {auth_b64}"},
            ) as ws,
        ):
            await ws.close()
    except aiohttp.WSServerHandshakeError as err:
        if err.status == 401:
            return "invalid_auth"
        _LOGGER.debug("Handshake error connecting to %s:%s", host, port, exc_info=True)
        return "cannot_connect"
    except aiohttp.ClientConnectionError, TimeoutError, OSError:
        _LOGGER.debug("Error connecting to %s:%s", host, port, exc_info=True)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error connecting to %s:%s", host, port)
        return "unknown"

    return None


class GardenaInclusionSubentryFlow(ConfigSubentryFlow):
    """Handle inclusion of a new device into an existing config entry."""

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> SubentryFlowResult:
        """Handle the first step of the inclusion subentry flow."""
        if user_input is not None:
            return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            last_step=False,
        )

    async def async_step_select(
        self, user_input: dict | None = None
    ) -> SubentryFlowResult:
        """Let the user pick which discovered device to include."""
        entry = self._get_entry()
        coordinator: GardenaSmartLocalCoordinator = entry.runtime_data
        devices = {k: v.device_name for k, v in coordinator.includable_devices.items()}

        if not devices:
            return self.async_abort(reason="no_devices_found")

        errors: dict[str, str] = {}

        if user_input is not None:
            instance_id = user_input["device"]
            device_id = await coordinator.async_include_device(instance_id)
            if device_id is not None:
                result = self.async_create_entry(
                    title=devices[instance_id],
                    data={"device_id": device_id},
                    unique_id=device_id,
                )
                # Broadcast coordinator update after _async_finish_flow adds the
                # subentry to entry.subentries, so _add_new_devices sees it.
                self.hass.loop.call_soon(
                    coordinator.async_set_updated_data, coordinator.data
                )
                return result
            errors["base"] = "inclusion_failed"

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema({vol.Required("device"): vol.In(devices)}),
            errors=errors,
        )
