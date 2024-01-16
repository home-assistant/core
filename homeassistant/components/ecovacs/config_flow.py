"""Config flow for Ecovacs mqtt integration."""
from __future__ import annotations

import logging
from typing import Any

from sucks import EcoVacsAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_CONTINENT, DOMAIN
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


def validate_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    errors: dict[str, str] = {}
    try:
        EcoVacsAPI(
            get_client_device_id(),
            user_input[CONF_USERNAME],
            EcoVacsAPI.md5(user_input[CONF_PASSWORD]),
            user_input[CONF_COUNTRY],
            user_input[CONF_CONTINENT],
        )
    except ValueError:
        errors["base"] = "invalid_auth"
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception")
        errors["base"] = "unknown"

    return errors


class EcovacsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ecovacs."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})

            errors = await self.hass.async_add_executor_job(validate_input, user_input)

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.TEXT
                            )
                        ),
                        vol.Required(CONF_PASSWORD): selector.TextSelector(
                            selector.TextSelectorConfig(
                                type=selector.TextSelectorType.PASSWORD
                            )
                        ),
                        vol.Required(CONF_COUNTRY): vol.All(vol.Lower, cv.string),
                        vol.Required(CONF_CONTINENT): vol.All(vol.Lower, cv.string),
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Import configuration from yaml."""

        def create_repair(error: str | None = None) -> None:
            if error:
                async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"deprecated_yaml_import_issue_{error}",
                    breaks_in_ha_version="2024.8.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key=f"deprecated_yaml_import_issue_{error}",
                    translation_placeholders={
                        "url": "/config/integrations/dashboard/add?domain=ecovacs"
                    },
                )
            else:
                async_create_issue(
                    self.hass,
                    HOMEASSISTANT_DOMAIN,
                    f"deprecated_yaml_{DOMAIN}",
                    breaks_in_ha_version="2024.8.0",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": "Ecovacs",
                    },
                )

        try:
            result = await self.async_step_user(user_input)
        except AbortFlow as ex:
            if ex.reason == "already_configured":
                create_repair()
            raise ex

        if errors := result.get("errors"):
            error = errors["base"]
            create_repair(error)
            return self.async_abort(reason=error)

        create_repair()
        return result
