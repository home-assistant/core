"""Config flow for ComfoConnect."""

from contextlib import suppress
from typing import Any, override

from pycomfoconnect import Bridge, ComfoConnect
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME, CONF_PIN, CONF_TOKEN

from .const import (
    CONF_USER_AGENT,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_TOKEN,
    DEFAULT_USER_AGENT,
    DOMAIN,
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid auth data."""


def _build_entry_data(
    data: dict[str, Any], include_name: bool = False
) -> dict[str, Any]:
    """Build normalized config entry data from user/import input.

    Args:
        data: Input data dictionary
        include_name: If True, include CONF_NAME from data (for YAML imports only)
    """
    entry = {
        CONF_HOST: data[CONF_HOST],
        CONF_MODEL: data.get(CONF_MODEL, DEFAULT_NAME),
        CONF_TOKEN: data.get(CONF_TOKEN, DEFAULT_TOKEN),
        CONF_USER_AGENT: data.get(CONF_USER_AGENT, DEFAULT_USER_AGENT),
        CONF_PIN: data.get(CONF_PIN, DEFAULT_PIN),
    }

    # Only include CONF_NAME for YAML imports, never for UI flows
    if include_name and CONF_NAME in data:
        entry[CONF_NAME] = data[CONF_NAME]

    return entry


class ComfoConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ComfoConnect."""

    VERSION = 1

    def _build_user_step_schema(self) -> vol.Schema:
        """Build the user step schema."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_MODEL, default=DEFAULT_NAME): str,
                vol.Optional(CONF_TOKEN, default=DEFAULT_TOKEN): vol.All(
                    str,
                    vol.Length(min=32, max=32),
                ),
                vol.Optional(CONF_USER_AGENT, default=DEFAULT_USER_AGENT): str,
                vol.Optional(CONF_PIN, default=f"{DEFAULT_PIN:04d}"): vol.All(
                    str,
                    vol.Length(min=4, max=4),
                    vol.Coerce(int),
                ),
            }
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # For UI flows, never include CONF_NAME
            entry_data = _build_entry_data(user_input, include_name=False)
            try:
                bridge = await self.hass.async_add_executor_job(
                    _validate_input, entry_data
                )
            except CannotConnect:
                errors["base"] = "Cannot_connect"
            except InvalidAuth:
                errors["base"] = "Invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "Unknown"
            else:
                await self.async_set_unique_id(bridge.uuid.hex())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=entry_data[CONF_MODEL],
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_step_schema(),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import YAML configuration into a config entry."""
        # For YAML imports, keep the CONF_NAME field so it can be used as device name
        entry_data = _build_entry_data(import_data, include_name=True)

        try:
            bridge = await self.hass.async_add_executor_job(_validate_input, entry_data)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")

        await self.async_set_unique_id(bridge.uuid.hex())
        self._abort_if_unique_id_configured(updates=entry_data)

        # Use CONF_NAME if available (YAML import), otherwise use CONF_MODEL
        title = entry_data.get(CONF_NAME, entry_data[CONF_MODEL])

        return self.async_create_entry(
            title=title,
            data=entry_data,
        )


def _validate_input(user_input: dict[str, Any]) -> Bridge:
    """Validate user input allows us to connect."""
    bridges = Bridge.discover(user_input[CONF_HOST])
    if not bridges:
        raise CannotConnect

    bridge = bridges[0]
    comfoconnect: ComfoConnect | None = None

    try:
        comfoconnect = ComfoConnect(
            bridge=bridge,
            local_uuid=bytes.fromhex(user_input[CONF_TOKEN]),
            local_devicename=user_input[CONF_USER_AGENT],
            pin=user_input[CONF_PIN],
        )
        comfoconnect.connect(True)
    except ValueError as err:
        raise InvalidAuth from err
    except Exception as err:
        msg = str(err).lower()
        if "auth" in msg or "pin" in msg or "token" in msg:
            raise InvalidAuth from err
        raise CannotConnect from err
    finally:
        if comfoconnect is not None:
            with suppress(Exception):
                comfoconnect.disconnect()

    return bridge
