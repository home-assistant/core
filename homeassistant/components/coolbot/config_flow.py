"""Config flow for the CoolBot Pro integration."""

import logging
from typing import Any, override

from pycoolbot import CoolbotAuthError, CoolbotClient, CoolbotError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CoolbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect credentials and confirm they work before creating the entry."""

    VERSION = 1

    async def _async_validate(self, email: str, password: str) -> str | None:
        """Return an error key, or None when the credentials work.

        An account with no CoolBot that has ever connected is refused, because
        the entry it created would have nothing in it.
        """
        session = async_get_clientsession(self.hass)
        client = CoolbotClient(email, password, session=session)
        try:
            await client.async_connect()
            devices = await client.async_get_devices(wait_for_live=False)
        except CoolbotAuthError:
            return "invalid_auth"
        except CoolbotError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating CoolBot credentials")
            return "unknown"
        else:
            if not any(device.is_provisioned for device in devices):
                return "no_devices"
            return None
        finally:
            await client.async_close()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial credentials step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]

            # The account is the natural identity; the service has no other id.
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            error = await self._async_validate(email, password)
            if error is None:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
