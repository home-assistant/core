"""Config flow for MELCloud Home."""

from collections.abc import Mapping
import logging
from typing import Any, override

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuth
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class MelCloudHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MELCloud Home."""

    async def _async_validate_credentials(
        self, email: str, password: str
    ) -> tuple[dict[str, str], str | None]:
        """Validate credentials against MELCloud Home API."""
        session = async_get_clientsession(self.hass)
        auth = MelCloudHomeAuth(username=email, password=password, session=session)
        client = MELCloudHome(auth=auth, session=session)

        errors: dict[str, str] = {}
        user_id: str | None = None

        try:
            context = await client.get_context()
        except MelCloudHomeAuthenticationError:
            errors["base"] = "invalid_auth"
        except MelCloudHomeConnectionError:
            errors["base"] = "cannot_connect"
        except MelCloudHomeTimeoutError:
            errors["base"] = "timeout_connect"
        except Exception:
            _LOGGER.exception(
                "Unexpected error while validating MELCloud Home credentials"
            )
            errors["base"] = "unknown"
        else:
            user_id = context.id

        return errors, user_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, user_id = await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth when MELCloud Home API authentication fails."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth: ask for new API token and validate."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors, user_id = await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            ),
            errors=errors,
        )
