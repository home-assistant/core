"""Music Player Daemon config flow."""

from asyncio import timeout
from contextlib import suppress
from socket import gaierror
from typing import Any, override

import mpd
from mpd.asyncio import MPDClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DEFAULT_PORT, DOMAIN, LOGGER

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

CONFIRM_SCHEMA = vol.Schema({vol.Optional(CONF_PASSWORD): str})


async def _async_try_connect(host: str, port: int, password: str | None) -> str | None:
    """Validate the connection and return an error key, or None on success."""
    client = MPDClient()
    client.timeout = 30
    client.idletimeout = 10
    try:
        async with timeout(35):
            await client.connect(host, port)
            if password is not None:
                await client.password(password)
    except TimeoutError, gaierror, mpd.ConnectionError, mpd.ProtocolError, OSError:
        return "cannot_connect"
    except mpd.CommandError:
        return "invalid_auth"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unknown exception")
        return "unknown"
    finally:
        with suppress(mpd.ConnectionError):
            client.disconnect()
    return None


class MPDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Music Player Daemon config flow."""

    _host: str
    _port: int
    _name: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            error = await _async_try_connect(
                user_input[CONF_HOST],
                user_input[CONF_PORT],
                user_input.get(CONF_PASSWORD),
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="Music Player Daemon",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        self._name = discovery_info.hostname.removesuffix(".local.") or self._host

        # MPD exposes no stable identifier, over zeroconf or its protocol.
        self._async_abort_entries_match({CONF_HOST: self._host, CONF_PORT: self._port})
        await self.async_set_unique_id(f"{self._host}:{self._port}")
        self._abort_if_unique_id_configured()

        if await _async_try_connect(self._host, self._port, None):
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a zeroconf discovered Music Player Daemon."""
        errors = {}
        # Submitting without a password yields an empty dict, not None.
        if user_input is not None:
            password = user_input.get(CONF_PASSWORD)
            error = await _async_try_connect(self._host, self._port, password)
            if error:
                errors["base"] = error
            else:
                data = {CONF_HOST: self._host, CONF_PORT: self._port}
                if password is not None:
                    data[CONF_PASSWORD] = password
                return self.async_create_entry(title=self._name, data=data)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=CONFIRM_SCHEMA,
            description_placeholders={"name": self._name},
            errors=errors,
        )
