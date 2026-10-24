"""Config flow for the Meraki integration."""

import logging
from typing import Any, override

from meraki import APIError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import async_create_client, is_auth_error
from .const import CONF_ORGANIZATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

API_KEY_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
)


class MerakiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meraki."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._api_key = ""
        self._organizations: dict[str, str] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            errors = await self._async_fetch_organizations(self._api_key)
            if not errors:
                if len(self._organizations) == 1:
                    return await self._async_create_organization_entry(
                        next(iter(self._organizations))
                    )
                return await self.async_step_organization()

        return self.async_show_form(
            step_id="user", data_schema=API_KEY_SCHEMA, errors=errors
        )

    async def async_step_organization(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose one of the organizations the API key can access."""
        if user_input is not None:
            return await self._async_create_organization_entry(
                user_input[CONF_ORGANIZATION_ID]
            )

        options = [
            SelectOptionDict(value=organization_id, label=name)
            for organization_id, name in sorted(
                self._organizations.items(), key=lambda item: item[1].lower()
            )
        ]
        return self.async_show_form(
            step_id="organization",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ORGANIZATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )

    async def _async_create_organization_entry(
        self, organization_id: str
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(organization_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._organizations[organization_id],
            data={CONF_API_KEY: self._api_key, CONF_ORGANIZATION_ID: organization_id},
        )

    async def _async_fetch_organizations(self, api_key: str) -> dict[str, str]:
        """Look up the organizations of an API key; return errors, if any."""
        try:
            async with await async_create_client(self.hass, api_key) as client:
                organizations = await client.organizations.getOrganizations(
                    total_pages="all"
                )
        except APIError as err:
            return {"base": "invalid_auth" if is_auth_error(err) else "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        if not organizations:
            return {"base": "no_organizations"}
        self._organizations = {
            organization["id"]: organization["name"] for organization in organizations
        }
        return {}
