"""Config flow for GARDENA smart local."""

import asyncio
import base64
import contextlib
import logging
from typing import override

import aiohttp
from cryptography import x509
import probatio
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.util.ssl import get_default_no_verify_context

from .const import DEFAULT_PORT, DOMAIN
from .coordinator import GardenaSmartLocalCoordinator

_LOGGER = logging.getLogger(__name__)

# A host pasted with surrounding whitespace is rejected by yarl; trim it in
# one place so every step stores and connects to the clean value.
# probatio.Strip keeps the form schema serializable for the frontend.
_HOST = probatio.All(str, probatio.Strip)


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
            host = user_input[CONF_HOST]
            unique_id = (
                await _async_extract_hostname_from_cert(host, user_input[CONF_PORT])
                or host
            )
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            # An entry added the other way round (zeroconf vs. manual), or one
            # created before the gateway certificate carried its name, uses the
            # host as its unique_id, so also match on host.
            self._async_abort_entries_match({CONF_HOST: host})

            error = await _async_try_connect(
                self.hass,
                host,
                user_input[CONF_PORT],
                user_input[CONF_PASSWORD],
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title=unique_id, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): _HOST,
                    probatio.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    probatio.Optional(CONF_PASSWORD, default=""): str,
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

        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        # A manually-added entry for the same host would have a different
        # (host based) unique_id, so also match on host.
        self._async_abort_entries_match({CONF_HOST: host})

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
                self.hass,
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
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST, default=self._discovered_host): _HOST,
                    probatio.Optional(
                        CONF_PORT, default=self._discovered_port
                    ): cv.port,
                    probatio.Optional(CONF_PASSWORD, default=""): str,
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
            if user_input[CONF_HOST] != entry.data.get(CONF_HOST):
                # Only a changed host can collide, and only with a different
                # entry: matching the current one would abort every save.
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            error = await _async_try_connect(
                self.hass,
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD, ""),
            )
            if error:
                errors["base"] = error
            else:
                unique_id = (
                    await _async_extract_hostname_from_cert(
                        user_input[CONF_HOST], user_input[CONF_PORT]
                    )
                    or entry.unique_id
                )
                return self.async_update_reload_and_abort(
                    entry, data=user_input, unique_id=unique_id
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_HOST, default=entry.data.get(CONF_HOST, "")
                    ): _HOST,
                    probatio.Optional(
                        CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ): cv.port,
                    probatio.Optional(
                        CONF_PASSWORD, default=entry.data.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors,
        )


async def _async_try_connect(
    hass: HomeAssistant, host: str, port: int, password: str
) -> str | None:
    """Try connecting to the gateway, returning an error string on failure."""
    ssl_context = get_default_no_verify_context()

    auth_b64 = base64.b64encode(f"_:{password}".encode()).decode("ascii")

    try:
        session = async_get_clientsession(hass)
        # ClientWSTimeout only bounds receive(); this probe never receives a
        # frame, so an unreachable host would otherwise hang on aiohttp's much
        # longer default. Cap the whole attempt.
        async with (
            asyncio.timeout(10),
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
    except ValueError:
        # yarl rejects a host that is empty or contains spaces/control chars.
        _LOGGER.debug("Invalid host %r", host)
        return "invalid_host"
    except Exception:
        _LOGGER.exception("Unexpected error connecting to %s:%s", host, port)
        return "unknown"

    return None


async def _async_extract_hostname_from_cert(host: str, port: int) -> str | None:
    """Return the hostname taken from the gateway's TLS certificate.

    The gateway certificate lists its mDNS hostname (``GARDENA-xxxxxx.local``) as a
    DNS name in the subjectAltName. That name is derived from the gateway's MAC
    address and survives a certificate regeneration, which makes it a stable
    unique_id that a manual and a discovered flow agree on. Return ``None`` when
    the gateway is unreachable or runs firmware whose certificate has no such name.
    """
    try:
        async with asyncio.timeout(10):
            _, writer = await asyncio.open_connection(
                host, port, ssl=get_default_no_verify_context()
            )
    except OSError, TimeoutError:
        _LOGGER.debug("Could not read the certificate of %s:%s", host, port)
        return None

    try:
        ssl_object = writer.get_extra_info("ssl_object")
        der = ssl_object.getpeercert(binary_form=True) if ssl_object else None
    finally:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()

    if not der:
        return None

    certificate = x509.load_der_x509_certificate(der)
    try:
        alt_names = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        )
    except x509.ExtensionNotFound:
        return None

    for dns_name in alt_names.value.get_values_for_type(x509.DNSName):
        if dns_name.endswith(".local"):
            return dns_name.removesuffix(".local")
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
            data_schema=probatio.Schema({}),
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
            data_schema=probatio.Schema(
                {probatio.Required("device"): probatio.In(devices)}
            ),
            errors=errors,
        )
