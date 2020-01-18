"""Config flow for Garmin Connect integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import (
    CONF_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from .const import DOMAIN
from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    GarminConnectAuthenticationError,
)

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class GarminConnectConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garmin Connect."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str,}
            ),
            errors=errors or {},
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}
        try:
            garmin = Garmin(user_input[CONF_USERNAME], user_input[CONF_PASSWORD],)
        except GarminConnectConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)
        except GarminConnectAuthenticationError:
            errors["base"] = "invalid_auth"
            return await self._show_setup_form(errors)
        except GarminConnectTooManyRequestsError:
            errors["base"] = "too_many_requests"
            return await self._show_setup_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return await self._show_setup_form(errors)

        try:
            unique_id = garmin.unique_id()
        except GarminConnectConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)
        except GarminConnectAuthenticationError:
            errors["base"] = "invalid_auth"
            return await self._show_setup_form(errors)
        except GarminConnectTooManyRequestsError:
            errors["base"] = "too_many_requests"
            return await self._show_setup_form(errors)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
            return await self._show_setup_form(errors)

        entries = self._async_current_entries()
        for entry in entries:
            if entry.data[CONF_ID] == unique_id:
                return self.async_abort(reason="already_setup")

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_ID: unique_id,
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
        )
