"""Will write later."""

import logging

from decora_wifi import DecoraWiFiSession
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class DecoreWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Decora Wifi Integration."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, str]) -> FlowResult:
        """Handle importting decora wifi config from configuration.yaml."""

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Decora Wifi",
            },
        )

        if CONF_USERNAME not in import_data or CONF_PASSWORD not in import_data:
            _LOGGER.error(
                "Could not import config data from yaml. Required Fields not found "
                "in decora_wifi config: %s, %s",
                CONF_USERNAME,
                CONF_PASSWORD,
            )
            # We don't have enough to auto-import, so skip to new setup
            return await self.async_step_user(None)

        return await self.async_step_user(import_data)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input["username"]
            password = user_input["password"]

            try:
                await async_validate_input(self.hass, username, password)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", exc)
                errors["base"] = "unknown"
            else:
                # No Errors
                unique_id = username.lower()
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
            step_id="user", data_schema=BASE_SCHEMA, errors=errors
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
