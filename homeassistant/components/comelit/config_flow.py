"""Config flow for Comelit integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiocomelit
import voluptuous as vol

from homeassistant import core, exceptions
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PIN
from homeassistant.data_entry_flow import FlowResult

from .const import _LOGGER, DEFAULT_HOST, DEFAULT_PIN, DOMAIN
from .coordinator import ComelitSerialBridge


def user_form_schema(user_input: dict[str, Any] | None) -> vol.Schema:
    """Return user form schema."""
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
            vol.Optional(CONF_PIN, default=DEFAULT_PIN): str,
        }
    )


STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PIN): str})


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows us to connect."""

    coordinator = ComelitSerialBridge(hass, data[CONF_HOST], data[CONF_PIN])

    try:
        await coordinator.api.login()
    except aiocomelit.exceptions.CannotConnect as err:
        raise CannotConnect from err
    except aiocomelit.exceptions.CannotAuthenticate as err:
        raise InvalidAuth from err

    await coordinator.api.logout()
    return {"title": data[CONF_HOST]}


class ComelitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comelit."""

    VERSION = 1
    entry: ConfigEntry | None = None
    hassio_discovery: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=user_form_schema(user_input)
            )

        self._async_abort_entries_match(
            {CONF_HOST: user_input[CONF_HOST], CONF_PIN: user_input[CONF_PIN]}
        )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=user_form_schema(user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth flow."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert self.entry
        self.context["title_placeholders"] = {"host": self.entry.data[CONF_HOST]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauth confirm."""
        assert self.entry
        errors = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, {**self.entry.data, **user_input})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_PIN: user_input[CONF_PIN],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_HOST: self.entry.data[CONF_HOST]},
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> FlowResult:
        """Handle the discovery step via hassio."""
        await self.async_set_unique_id("hassio")
        self._abort_if_unique_id_configured(discovery_info.config)

        self.hassio_discovery = discovery_info.config
        self.context["title_placeholders"] = {"host": discovery_info.config[CONF_HOST]}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Supervisor discovery."""
        assert self.hassio_discovery
        if user_input is None:
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self.hassio_discovery["addon"]},
            )

        self.hassio_discovery.pop("addon")

        try:
            info = await validate_input(self.hass, self.hassio_discovery)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(title=info["title"], data=self.hassio_discovery)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
