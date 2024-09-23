"""Config flow for motionEye integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from motioneye_client.client import (
    MotionEyeClientConnectionError,
    MotionEyeClientInvalidAuthError,
    MotionEyeClientRequestError,
)
import voluptuous as vol

from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_SOURCE, CONF_URL, CONF_WEBHOOK_ID
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import VolDictType

from . import create_motioneye_client
from .const import (
    CONF_ADMIN_PASSWORD,
    CONF_ADMIN_USERNAME,
    CONF_STREAM_URL_TEMPLATE,
    CONF_SURVEILLANCE_PASSWORD,
    CONF_SURVEILLANCE_USERNAME,
    CONF_WEBHOOK_SET,
    CONF_WEBHOOK_SET_OVERWRITE,
    DEFAULT_WEBHOOK_SET,
    DEFAULT_WEBHOOK_SET_OVERWRITE,
    DOMAIN,
)


class MotionEyeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for motionEye."""

    VERSION = 1
    _hassio_discovery: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        def _get_form(
            user_input: dict[str, Any], errors: dict[str, str] | None = None
        ) -> ConfigFlowResult:
            """Show the form to the user."""
            url_schema: VolDictType = {}
            if not self._hassio_discovery:
                # Only ask for URL when not discovered
                url_schema[
                    vol.Required(CONF_URL, default=user_input.get(CONF_URL, ""))
                ] = str

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        **url_schema,
                        vol.Optional(
                            CONF_ADMIN_USERNAME,
                            default=user_input.get(CONF_ADMIN_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_ADMIN_PASSWORD,
                            default=user_input.get(CONF_ADMIN_PASSWORD, ""),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_USERNAME,
                            default=user_input.get(CONF_SURVEILLANCE_USERNAME),
                        ): str,
                        vol.Optional(
                            CONF_SURVEILLANCE_PASSWORD,
                            default=user_input.get(CONF_SURVEILLANCE_PASSWORD, ""),
                        ): str,
                    }
                ),
                errors=errors,
            )

        reauth_entry = None
        if self.context.get("entry_id"):
            reauth_entry = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )

        if user_input is None:
            return _get_form(
                cast(dict[str, Any], reauth_entry.data) if reauth_entry else {}
            )

        if self._hassio_discovery:
            # In case of Supervisor discovery, use pushed URL
            user_input[CONF_URL] = self._hassio_discovery[CONF_URL]

        try:
            # Cannot use cv.url validation in the schema itself, so
            # apply extra validation here.
            cv.url(user_input[CONF_URL])
        except vol.Invalid:
            return _get_form(user_input, {"base": "invalid_url"})

        client = create_motioneye_client(
            user_input[CONF_URL],
            admin_username=user_input.get(CONF_ADMIN_USERNAME),
            admin_password=user_input.get(CONF_ADMIN_PASSWORD),
            surveillance_username=user_input.get(CONF_SURVEILLANCE_USERNAME),
            surveillance_password=user_input.get(CONF_SURVEILLANCE_PASSWORD),
            session=async_get_clientsession(self.hass),
        )

        errors = {}
        try:
            await client.async_client_login()
        except MotionEyeClientConnectionError:
            errors["base"] = "cannot_connect"
        except MotionEyeClientInvalidAuthError:
            errors["base"] = "invalid_auth"
        except MotionEyeClientRequestError:
            errors["base"] = "unknown"
        finally:
            await client.async_client_close()

        if errors:
            return _get_form(user_input, errors)

        if self.context.get(CONF_SOURCE) == SOURCE_REAUTH and reauth_entry is not None:
            # Persist the same webhook id across reauths.
            if CONF_WEBHOOK_ID in reauth_entry.data:
                user_input[CONF_WEBHOOK_ID] = reauth_entry.data[CONF_WEBHOOK_ID]
            self.hass.config_entries.async_update_entry(reauth_entry, data=user_input)
            # Need to manually reload, as the listener won't have been
            # installed because the initial load did not succeed (the reauth
            # flow will not be initiated if the load succeeds).
            await self.hass.config_entries.async_reload(reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        # Search for duplicates: there isn't a useful unique_id, but
        # at least prevent entries with the same motionEye URL.
        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

        title = user_input[CONF_URL]
        if self._hassio_discovery:
            title = "Add-on"

        return self.async_create_entry(
            title=title,
            data=user_input,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthentication flow."""
        return await self.async_step_user()

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle Supervisor discovery."""
        self._hassio_discovery = discovery_info.config
        await self._async_handle_discovery_without_unique_id()

        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Supervisor discovery."""
        if user_input is None and self._hassio_discovery is not None:
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={"addon": self._hassio_discovery["addon"]},
            )

        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MotionEyeOptionsFlow:
        """Get the Hyperion Options flow."""
        return MotionEyeOptionsFlow(config_entry)


class MotionEyeOptionsFlow(OptionsFlow):
    """motionEye options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize a motionEye options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema: dict[vol.Marker, type] = {
            vol.Required(
                CONF_WEBHOOK_SET,
                default=self._config_entry.options.get(
                    CONF_WEBHOOK_SET,
                    DEFAULT_WEBHOOK_SET,
                ),
            ): bool,
            vol.Required(
                CONF_WEBHOOK_SET_OVERWRITE,
                default=self._config_entry.options.get(
                    CONF_WEBHOOK_SET_OVERWRITE,
                    DEFAULT_WEBHOOK_SET_OVERWRITE,
                ),
            ): bool,
        }

        if self.show_advanced_options:
            # The input URL is not validated as being a URL, to allow for the possibility
            # the template input won't be a valid URL until after it's rendered
            description: dict[str, str] | None = None
            if CONF_STREAM_URL_TEMPLATE in self._config_entry.options:
                description = {
                    "suggested_value": self._config_entry.options[
                        CONF_STREAM_URL_TEMPLATE
                    ]
                }

            schema[vol.Optional(CONF_STREAM_URL_TEMPLATE, description=description)] = (
                str
            )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))
