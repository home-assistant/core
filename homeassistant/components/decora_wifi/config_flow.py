"""Config flow for Decora Wifi integration."""

import logging
from typing import Any

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
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
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

        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

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
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=username,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=BASE_SCHEMA, errors=errors
        )


async def async_validate_input(
    hass: HomeAssistant, username: str, password: str
) -> None:
    """Validate user input. Will throw if cannot authenticated with provided credentials."""
    session = DecoraWiFiSession()
    try:
        user = await hass.async_add_executor_job(session.login, username, password)
    # As of the current release of the decora wifi lib (1.4), all api errors raise a generic ValueError
    except ValueError as err:
        raise CannotConnect("request failed") from err
    if not user:
        raise InvalidAuth("invalid authentication")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
