"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from aiohttp import ClientError
from pydrawise import auth, client, legacy
from pydrawise.exceptions import NotAuthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, LOGGER


class HydrawiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Construct a ConfigFlow."""
        self.reauth_entry: ConfigEntry | None = None

    async def _create_or_update_entry(
        self,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        *,
        on_failure: Callable[[str], ConfigFlowResult],
    ) -> ConfigFlowResult:
        """Create the config entry."""

        # Verify that the provided credentials work."""
        if api_key:
            api = legacy.LegacyHydrawiseAsync(api_key)
        else:
            api = client.Hydrawise(auth.Auth(username, password))
        try:
            # Skip fetching zones to save on metered API calls.
            user = await api.get_user()
        except NotAuthorizedError:
            return on_failure("invalid_auth")
        except TimeoutError:
            return on_failure("timeout_connect")
        except ClientError as ex:
            LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
            return on_failure("cannot_connect")

        await self.async_set_unique_id(f"hydrawise-{user.customer_id}")

        if not self.reauth_entry:
            self._abort_if_unique_id_configured()

            # We are creating an entry for username/password even if we
            # import a legacy YAML file. This will require users to immediately
            # re-authenticate.
            return self.async_create_entry(
                title="Hydrawise",
                data={CONF_API_KEY: api_key}
                if api_key
                else {CONF_USERNAME: username, CONF_PASSWORD: password},
            )

        self.reauth_entry.minor_version = self.MINOR_VERSION
        self.hass.config_entries.async_update_entry(
            self.reauth_entry,
            data=self.reauth_entry.data
            | {CONF_USERNAME: username, CONF_PASSWORD: password},
        )
        await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    def _import_issue(self, error_type: str) -> ConfigFlowResult:
        """Create an issue about a YAML import failure."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{error_type}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            severity=IssueSeverity.ERROR,
            translation_key="deprecated_yaml_import_issue",
            translation_placeholders={
                "error_type": error_type,
                "url": "/config/integrations/dashboard/add?domain=hydrawise",
            },
        )
        return self.async_abort(reason=error_type)

    def _deprecated_yaml_issue(self) -> None:
        """Create an issue about YAML deprecation."""
        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Hydrawise",
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup."""
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            return await self._create_or_update_entry(
                username=username, password=password, on_failure=self._show_form
            )
        return self._show_form()

    def _show_form(self, error_type: str | None = None) -> ConfigFlowResult:
        errors = {}
        if error_type is not None:
            errors["base"] = error_type
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth after updating config to username/password."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_user()

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import data from YAML."""
        try:
            result = await self._create_or_update_entry(
                api_key=import_data.get(CONF_API_KEY, ""),
                on_failure=self._import_issue,
            )
        except AbortFlow:
            self._deprecated_yaml_issue()
            raise

        if result["type"] == FlowResultType.CREATE_ENTRY:
            self._deprecated_yaml_issue()
        return result
