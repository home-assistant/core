"""Config flow to configure the LG Netcast TV integration."""
from __future__ import annotations

from typing import Any

from pylgnetcast import AccessTokenError, LgNetCastClient, SessionIdError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_ID, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.util.network import is_host_valid

from .const import DEFAULT_NAME, DOMAIN
from .helpers import LGNetCastDetailDiscoveryError, async_discover_netcast_details


class LGNetCast(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LG Netcast TV integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self.client: LgNetCastClient | None = None
        self.device_config: dict[str, Any] = {}
        self._discovered_devices: dict[str, Any] = {}

    def create_client(self) -> None:
        """Create LG Netcast client from config."""
        host = self.device_config[CONF_HOST]
        access_token = self.device_config.get(CONF_ACCESS_TOKEN)
        self.client = LgNetCastClient(host, access_token)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            if is_host_valid(host):
                self.device_config[CONF_HOST] = host
                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import configuration from yaml."""
        self.device_config = {
            CONF_HOST: config[CONF_HOST],
            CONF_NAME: config[CONF_NAME],
            CONF_ID: config[CONF_ID],
        }
        try:
            self._async_abort_entries_match({CONF_ID: config[CONF_ID]})
        except AbortFlow as err:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_already_configured",
                breaks_in_ha_version="2024.6.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_already_configured",
                translation_placeholders={
                    "domain": DOMAIN,
                    "interation_title": "LG Netcast",
                },
            )
            raise err

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
                "integration_title": "LG Netcast",
            },
        )

        return await self.async_step_authorize(config)

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle Authorize step."""
        errors: dict[str, str] = {}

        if user_input is not None and user_input.get(CONF_ACCESS_TOKEN) is not None:
            self.device_config[CONF_ACCESS_TOKEN] = user_input[CONF_ACCESS_TOKEN]

        self.create_client()
        assert self.client is not None

        if not self.device_config.get(CONF_ID):
            try:
                details = await async_discover_netcast_details(self.hass, self.client)
            except LGNetCastDetailDiscoveryError:
                return self.async_abort(reason="cannot_connect")
            unique_id = details["uuid"]
            if unique_id is None:
                return self.async_abort(reason="invalid_host")
            self.device_config[CONF_ID] = unique_id
            if CONF_NAME not in self.device_config:
                model_name = details["model_name"]
                friendly_name = details["friendly_name"] or DEFAULT_NAME
                self.device_config[CONF_NAME] = (
                    f"{friendly_name} ({model_name})" if model_name else friendly_name
                )

        await self.async_set_unique_id(self.device_config[CONF_ID])
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: self.device_config[CONF_HOST]}
        )

        try:
            await self.hass.async_add_executor_job(
                self.client._get_session_id  # pylint: disable=protected-access
            )
            return await self.async_create_device()
        except AccessTokenError:
            if user_input is not None:
                errors[CONF_ACCESS_TOKEN] = "invalid_access_token"
        except SessionIdError:
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ACCESS_TOKEN): vol.All(str, vol.Length(max=6)),
                }
            ),
            errors=errors,
        )

    async def async_create_device(self) -> FlowResult:
        """Create LG Netcast TV Device from config."""
        assert self.client

        return self.async_create_entry(
            title=self.device_config[CONF_NAME], data=self.device_config
        )
