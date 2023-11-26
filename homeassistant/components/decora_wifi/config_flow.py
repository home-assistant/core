"""Will write later."""

import logging

from decora_wifi import DecoraWiFiSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class DecoreWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Decora Wifi Integration."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, str]) -> FlowResult:
        """Import decora wifi config from configuration.yaml."""

        if CONF_USERNAME not in import_data or CONF_PASSWORD not in import_data:
            _LOGGER.error(
                "Could not import config data from yaml. Required Fields not found: %s, %s",
                CONF_USERNAME,
                CONF_PASSWORD,
            )
            return await self.async_step_user(None)

        return self.async_create_entry(
            title=CONF_USERNAME,
            data={CONF_USERNAME: CONF_USERNAME, CONF_PASSWORD: CONF_PASSWORD},
        )

    # From components/vera
    # async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
    #     """Handle a flow initialized by import."""

    #     # If there are entities with the legacy unique_id, then this imported config
    #     # should also use the legacy unique_id for entity creation.
    #     entity_registry = er.async_get(self.hass)
    #     use_legacy_unique_id = (
    #         len(
    #             [
    #                 entry
    #                 for entry in entity_registry.entities.values()
    #                 if entry.platform == DOMAIN and entry.unique_id.isdigit()
    #             ]
    #         )
    #         > 0
    #     )

    #     return await self.async_step_finish(
    #         {
    #             **config,
    #             **{CONF_SOURCE: config_entries.SOURCE_IMPORT},
    #             **{CONF_LEGACY_UNIQUE_ID: use_legacy_unique_id},
    #         }
    #     )

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            try:
                await async_validate_input(self.hass, username, password)
                unique_id = username.lower()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", exc)
                errors["base"] = "unknown"
            else:
                # No Errors
                existing_entry = await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=user_input
                    )
                    # Reload the config entry otherwise devices will remain unavailable
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(existing_entry.entry_id)
                    )

                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


async def async_validate_input(
    hass: HomeAssistant, username: str, password: str
) -> None:
    """Validate user input. Will throw if cannot authenticated with provided credentials."""
    session = DecoraWiFiSession()
    user = await hass.async_add_executor_job(lambda: session.login(username, password))
    if not user:
        raise InvalidAuth("invalid authentication")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
