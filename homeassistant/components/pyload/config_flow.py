"""Config flow for pyLoad integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import CookieJar
from pyloadapi import CannotConnect, InvalidAuth, ParserError, PyLoadAPI
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
                autocomplete="url",
            ),
        ),
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.TEXT,
                autocomplete="username",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)
PLACEHOLDER = {"example_url": "https://example.com:8000/path"}


async def validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    """Validate the user input and try to connect to PyLoad."""

    session = async_create_clientsession(
        hass,
        user_input[CONF_VERIFY_SSL],
        cookie_jar=CookieJar(unsafe=True),
    )
    pyload = PyLoadAPI(
        session,
        api_url=URL(user_input[CONF_URL]),
        username=user_input[CONF_USERNAME],
        password=user_input[CONF_PASSWORD],
    )

    await pyload.login()


class PyLoadConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pyLoad."""

    VERSION = 1
    MINOR_VERSION = 1

    _hassio_discovery: HassioServiceInfo | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            url = URL(user_input[CONF_URL]).human_repr()
            self._async_abort_entries_match({CONF_URL: url})
            try:
                await validate_input(self.hass, user_input)
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                title = DEFAULT_NAME

                return self.async_create_entry(
                    title=title,
                    data={
                        **user_input,
                        CONF_URL: url,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders=PLACEHOLDER,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, {**reauth_entry.data, **user_input})
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA,
                {
                    CONF_USERNAME: user_input[CONF_USERNAME]
                    if user_input is not None
                    else reauth_entry.data[CONF_USERNAME]
                },
            ),
            description_placeholders={CONF_NAME: reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfiguration flow."""
        errors = {}
        reconfig_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except (CannotConnect, ParserError):
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reconfig_entry,
                    data={
                        **user_input,
                        CONF_URL: URL(user_input[CONF_URL]).human_repr(),
                    },
                    reload_even_if_entry_is_unchanged=False,
                )
        suggested_values = user_input if user_input else reconfig_entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                suggested_values,
            ),
            description_placeholders={
                CONF_NAME: reconfig_entry.data[CONF_USERNAME],
                **PLACEHOLDER,
            },
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for pyLoad add-on.

        This flow is triggered by the discovery component.
        """
        url = URL(discovery_info.config[CONF_URL]).human_repr()
        self._async_abort_entries_match({CONF_URL: url})
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(updates={CONF_URL: url})
        discovery_info.config[CONF_URL] = url
        self._hassio_discovery = discovery_info
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        assert self._hassio_discovery
        errors: dict[str, str] = {}

        data = {**self._hassio_discovery.config, CONF_VERIFY_SSL: False}

        if user_input is not None:
            data.update(user_input)

        try:
            await validate_input(self.hass, data)
        except (CannotConnect, ParserError):
            _LOGGER.debug("Cannot connect", exc_info=True)
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if user_input is None:
                self._set_confirm_only()
                return self.async_show_form(
                    step_id="hassio_confirm",
                    description_placeholders=self._hassio_discovery.config,
                )
            return self.async_create_entry(title=self._hassio_discovery.slug, data=data)

        return self.async_show_form(
            step_id="hassio_confirm",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=REAUTH_SCHEMA, suggested_values=data
            ),
            description_placeholders=self._hassio_discovery.config,
            errors=errors if user_input is not None else None,
        )
