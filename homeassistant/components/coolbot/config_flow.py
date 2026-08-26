"""Config flow for the CoolBot Pro integration."""

from collections.abc import Mapping
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

    def __init__(self) -> None:
        """Initialize the flow."""
        self._reauth_email: str | None = None

    async def _async_validate(self, email: str, password: str) -> str | None:
        """Return an error key, or None when the credentials work."""
        session = async_get_clientsession(self.hass)
        client = CoolbotClient(email, password, session=session)
        try:
            await client.async_connect()
            # A working login is not enough; an account with no CoolBot would
            # produce an integration with nothing in it.
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
            # A failed close must not replace the flow's real outcome.
            try:
                await client.async_close()
            except Exception:
                _LOGGER.debug("Error while closing the socket", exc_info=True)

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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user re-enter credentials without deleting the entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            # The entry's identity is the account; pointing it at a different
            # account would orphan every existing entity, so require adding a
            # new entry for that instead.
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_mismatch(reason="account_mismatch")

            error = await self._async_validate(email, user_input[CONF_PASSWORD])
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, {CONF_EMAIL: entry.data[CONF_EMAIL]}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth, triggered when the stored password stops working."""
        self._reauth_email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for and validate a replacement password."""
        errors: dict[str, str] = {}
        assert self._reauth_email is not None

        if user_input is not None:
            error = await self._async_validate(
                self._reauth_email, user_input[CONF_PASSWORD]
            )
            if error is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": self._reauth_email},
            errors=errors,
        )
