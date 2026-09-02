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
            # MPD greets before authenticating, so a read is what proves the
            # credentials actually grant access.
            await client.status()
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
    _discovered_hosts: tuple[str, ...]

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

    def _async_abort_discovered_entries_match(self) -> None:
        """Abort if any host the discovered server answers to is configured."""
        for host in self._discovered_hosts:
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: self._port})

    @override
    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT
        hostname = discovery_info.hostname.rstrip(".")
        self._name = hostname.removesuffix(".local") or self._host

        # Entries may be configured under any address the server advertises or
        # under its hostname, and a dual-stack server can present a different
        # one on each announcement, so match them all.
        self._discovered_hosts = (*discovery_info.addresses, hostname, self._name)
        self._async_abort_discovered_entries_match()
        # MPD exposes no identifier tied to the device, so the entry gets no
        # unique id. The hostname deduplicates flows for one server: unlike the
        # selected address it survives dual-stack reannouncements, and unlike the
        # DNS-SD instance name it survives a restart, which MPD renames by
        # appending its pid. It is cleared before the entry is created.
        await self.async_set_unique_id(f"{hostname}:{self._port}")
        self._abort_if_unique_id_configured()

        # A server that needs a password fails the unauthenticated probe, so
        # only a transport failure rules the server out here.
        if await _async_try_connect(self._host, self._port, None) == "cannot_connect":
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
                # The entry may have been created by hand while this form was
                # open, and clearing the unique id drops the only other guard.
                self._async_abort_discovered_entries_match()
                data = {CONF_HOST: self._host, CONF_PORT: self._port}
                if password is not None:
                    data[CONF_PASSWORD] = password
                await self.async_set_unique_id(None)
                return self.async_create_entry(title=self._name, data=data)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=CONFIRM_SCHEMA,
            description_placeholders={"name": self._name},
            errors=errors,
        )
