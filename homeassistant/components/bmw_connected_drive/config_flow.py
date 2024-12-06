"""Config flow for BMW ConnectedDrive integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bimmer_connected.api.authentication import MyBMWAuthentication
from bimmer_connected.api.regions import get_region_from_name
from bimmer_connected.models import (
    MyBMWAPIError,
    MyBMWAuthError,
    MyBMWCaptchaMissingError,
)
from httpx import RequestError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_SOURCE, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.util.ssl import get_default_context

from . import DOMAIN
from .const import (
    CONF_ALLOWED_REGIONS,
    CONF_CAPTCHA_REGIONS,
    CONF_CAPTCHA_TOKEN,
    CONF_CAPTCHA_URL,
    CONF_GCID,
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(
                options=CONF_ALLOWED_REGIONS,
                translation_key="regions",
            )
        ),
    },
    extra=vol.REMOVE_EXTRA,
)
CAPTCHA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CAPTCHA_TOKEN): str,
    },
    extra=vol.REMOVE_EXTRA,
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    auth = MyBMWAuthentication(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        get_region_from_name(data[CONF_REGION]),
        hcaptcha_token=data.get(CONF_CAPTCHA_TOKEN),
        verify=get_default_context(),
    )

    try:
        await auth.login()
    except MyBMWCaptchaMissingError as ex:
        raise MissingCaptcha from ex
    except MyBMWAuthError as ex:
        raise InvalidAuth from ex
    except (MyBMWAPIError, RequestError) as ex:
        raise CannotConnect from ex

    # Return info that you want to store in the config entry.
    retval = {"title": f"{data[CONF_USERNAME]}{data.get(CONF_SOURCE, '')}"}
    if auth.refresh_token:
        retval[CONF_REFRESH_TOKEN] = auth.refresh_token
    if auth.gcid:
        retval[CONF_GCID] = auth.gcid
    return retval


class BMWConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyBMW."""

    VERSION = 1

    data: dict[str, Any] = {}

    _existing_entry_data: Mapping[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = self.data.pop("errors", {})

        if user_input is not None and not errors:
            unique_id = f"{user_input[CONF_REGION]}-{user_input[CONF_USERNAME]}"
            await self.async_set_unique_id(unique_id)

            if self.source in {SOURCE_REAUTH, SOURCE_RECONFIGURE}:
                self._abort_if_unique_id_mismatch(reason="account_mismatch")
            else:
                self._abort_if_unique_id_configured()

            # Store user input for later use
            self.data.update(user_input)

            # North America and Rest of World require captcha token
            if (
                self.data.get(CONF_REGION) in CONF_CAPTCHA_REGIONS
                and CONF_CAPTCHA_TOKEN not in self.data
            ):
                return await self.async_step_captcha()

            info = None
            try:
                info = await validate_input(self.hass, self.data)
            except MissingCaptcha:
                errors["base"] = "missing_captcha"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            finally:
                self.data.pop(CONF_CAPTCHA_TOKEN, None)

            if info:
                entry_data = {
                    **self.data,
                    CONF_REFRESH_TOKEN: info.get(CONF_REFRESH_TOKEN),
                    CONF_GCID: info.get(CONF_GCID),
                }

                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=entry_data
                    )
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data=entry_data,
                    )
                return self.async_create_entry(
                    title=info["title"],
                    data=entry_data,
                )

        schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA,
            self._existing_entry_data or self.data,
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self._existing_entry_data = entry_data
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        self._existing_entry_data = self._get_reconfigure_entry().data
        return await self.async_step_user()

    async def async_step_captcha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show captcha form."""
        if user_input and user_input.get(CONF_CAPTCHA_TOKEN):
            self.data[CONF_CAPTCHA_TOKEN] = user_input[CONF_CAPTCHA_TOKEN].strip()
            return await self.async_step_user(self.data)

        return self.async_show_form(
            step_id="captcha",
            data_schema=CAPTCHA_SCHEMA,
            description_placeholders={
                "captcha_url": CONF_CAPTCHA_URL.format(region=self.data[CONF_REGION])
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BMWOptionsFlow:
        """Return a MyBMW option flow."""
        return BMWOptionsFlow()


class BMWOptionsFlow(OptionsFlow):
    """Handle a option flow for MyBMW."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_account_options()

    async def async_step_account_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Manually update & reload the config entry after options change.
            # Required as each successful login will store the latest refresh_token
            # using async_update_entry, which would otherwise trigger a full reload
            # if the options would be refreshed using a listener.
            changed = self.hass.config_entries.async_update_entry(
                self.config_entry,
                options=user_input,
            )
            if changed:
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="account_options",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_READ_ONLY,
                        default=self.config_entry.options.get(CONF_READ_ONLY, False),
                    ): bool,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MissingCaptcha(HomeAssistantError):
    """Error to indicate the captcha token is missing."""
