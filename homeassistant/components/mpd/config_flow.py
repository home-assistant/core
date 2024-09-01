"""Music Player Daemon config flow."""

from asyncio import timeout
from contextlib import suppress
from socket import gaierror
from typing import Any

import mpd
from mpd.asyncio import MPDClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT

from .const import DOMAIN, LOGGER

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_PORT, default=6600): int,
    }
)


class MPDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Music Player Daemon config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            client = MPDClient()
            client.timeout = 30
            client.idletimeout = 10
            try:
                async with timeout(35):
                    await client.connect(user_input[CONF_HOST], user_input[CONF_PORT])
                    if CONF_PASSWORD in user_input:
                        await client.password(user_input[CONF_PASSWORD])
                    with suppress(mpd.ConnectionError):
                        client.disconnect()
            except (
                TimeoutError,
                gaierror,
                mpd.ConnectionError,
                OSError,
            ):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"
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

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Attempt to import the existing configuration."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        client = MPDClient()
        client.timeout = 30
        client.idletimeout = 10
        try:
            async with timeout(35):
                await client.connect(import_data[CONF_HOST], import_data[CONF_PORT])
                if CONF_PASSWORD in import_data:
                    await client.password(import_data[CONF_PASSWORD])
                with suppress(mpd.ConnectionError):
                    client.disconnect()
        except (
            TimeoutError,
            gaierror,
            mpd.ConnectionError,
            OSError,
        ):
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unknown exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=import_data.get(CONF_NAME, "Music Player Daemon"),
            data={
                CONF_HOST: import_data[CONF_HOST],
                CONF_PORT: import_data[CONF_PORT],
                CONF_PASSWORD: import_data.get(CONF_PASSWORD),
            },
        )
