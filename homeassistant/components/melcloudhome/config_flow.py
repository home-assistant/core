"""Config flow for MELCloud Home."""

import logging
from typing import Any

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
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class MelCloudHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MELCloud Home."""

    async def _async_validate_credentials(
        self, email: str, password: str
    ) -> dict[str, str]:
        """Validate credentials against MELCloud Home API."""
        session = async_get_clientsession(self.hass)
        auth = MelCloudHomeAuth(username=email, password=password, session=session)
        client = MELCloudHome(auth=auth, session=session)

        errors: dict[str, str] = {}

        try:
            await client.get_context()
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
        finally:
            await auth.close()

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
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
