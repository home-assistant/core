"""Config flow for Fujitsu HVAC (based on Ayla IOT) integration."""

from collections.abc import Mapping
import logging
from typing import Any

from ayla_iot_unofficial import AylaAuthError, new_ayla_api
from ayla_iot_unofficial.fujitsu_consts import FGLAIR_APP_CREDENTIALS
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from .const import API_TIMEOUT, CONF_REGION, DOMAIN, REGION_DEFAULT, REGION_EU

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION, default=REGION_DEFAULT): SelectSelector(
            SelectSelectorConfig(
                options=[region.lower() for region in FGLAIR_APP_CREDENTIALS],
                translation_key=CONF_REGION,
            )
        ),
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class FGLairConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fujitsu HVAC (based on Ayla IOT)."""

    MINOR_VERSION = 2

    async def _async_validate_credentials(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        app_id, app_secret = FGLAIR_APP_CREDENTIALS[user_input[CONF_REGION]]
        api = new_ayla_api(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            app_id,
            app_secret,
            europe=user_input[CONF_REGION] == REGION_EU,
            websession=aiohttp_client.async_get_clientsession(self.hass),
            timeout=API_TIMEOUT,
        )
        try:
            await api.async_sign_in()
        except TimeoutError:
            errors["base"] = "cannot_connect"
        except AylaAuthError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_credentials(user_input)
            if not errors:
                return self.async_create_entry(
                    title=f"FGLair ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input:
            errors = await self._async_validate_credentials(
                reauth_entry.data | user_input
            )

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                **self.context["title_placeholders"],
            },
            errors=errors,
        )
