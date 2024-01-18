"""Config flow for Ecovacs mqtt integration."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from deebot_client.authentication import Authenticator
from deebot_client.exceptions import InvalidAuthenticationError
from deebot_client.models import Configuration
from deebot_client.util import md5
from deebot_client.util.continents import get_continent
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import aiohttp_client, selector
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_CONTINENT, DOMAIN
from .util import get_client_device_id

_LOGGER = logging.getLogger(__name__)


async def _validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str]:
    """Validate user input."""
    errors: dict[str, str] = {}

    deebot_config = Configuration(
        aiohttp_client.async_get_clientsession(hass),
        device_id=get_client_device_id(),
        country=user_input[CONF_COUNTRY],
        continent=user_input.get(CONF_CONTINENT),
    )

    authenticator = Authenticator(
        deebot_config,
        user_input[CONF_USERNAME],
        md5(user_input[CONF_PASSWORD]),
    )

    try:
        await authenticator.authenticate()
    except ClientError:
        _LOGGER.debug("Cannot connect", exc_info=True)
        errors["base"] = "cannot_connect"
    except InvalidAuthenticationError:
        errors["base"] = "invalid_auth"
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception("Unexpected exception during login")
        errors["base"] = "unknown"

    if (continent := user_input.get(CONF_CONTINENT)) and len(continent) != 2:
        errors["CONF_CONTINENT"] = "invalid_continent_length"

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

            errors = await _validate_input(self.hass, user_input)

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
                        vol.Required(CONF_COUNTRY): selector.CountrySelector(),
                        vol.Optional(CONF_CONTINENT): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=["as", "eu", "na", "ww"],
                                translation_key=CONF_CONTINENT,
                                custom_value=True,
                                sort=True,
                            )
                        ),
                    }
                ),
                user_input
                or {
                    CONF_COUNTRY: self.hass.config.country,
                    CONF_CONTINENT: get_continent(self.hass.config.country),
                },
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
