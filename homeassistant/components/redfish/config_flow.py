"""Config flow for Redfish."""

from collections.abc import Mapping
import logging
from typing import Any, override

import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import RedfishApi, RedfishAuthError, RedfishError
from .const import CONF_BASE_URL, DEFAULT_VERIFY_SSL, DOMAIN
from .models import RedfishSystem

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL, autocomplete="url")
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def normalize_base_url(value: str) -> str:
    """Validate and normalize a Redfish base URL."""
    try:
        url = URL(value)
    except (TypeError, ValueError) as err:
        raise vol.Invalid("Invalid Redfish base URL") from err
    if (
        url.scheme != "https"
        or url.host is None
        or url.user is not None
        or url.password is not None
        or url.path not in {"", "/"}
        or url.query_string
        or url.fragment
    ):
        raise vol.Invalid("Invalid Redfish base URL")
    return str(url.with_path("").with_query(None).with_fragment(None)).rstrip("/")


class RedfishConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Redfish config flow."""

    VERSION = 1

    async def _async_get_systems(
        self, data: Mapping[str, Any]
    ) -> dict[str, RedfishSystem]:
        """Authenticate and discover Redfish systems."""
        client = RedfishApi(
            async_get_clientsession(self.hass, verify_ssl=data[CONF_VERIFY_SSL]),
            data[CONF_BASE_URL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        await client.async_login()
        return await client.async_get_systems()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_BASE_URL])
            except vol.Invalid:
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                normalized_input = {**user_input, CONF_BASE_URL: base_url}
                await self.async_set_unique_id(base_url)
                self._abort_if_unique_id_configured()
                try:
                    systems = await self._async_get_systems(normalized_input)
                except ValueError, RedfishAuthError:
                    errors["base"] = "invalid_auth"
                except RedfishError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected exception validating Redfish service")
                    errors["base"] = "unknown"
                else:
                    if not systems:
                        errors["base"] = "no_systems"
                    else:
                        first_system = next(iter(systems.values()))
                        return self.async_create_entry(
                            title=first_system.name or base_url,
                            data=normalized_input,
                        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate updated credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                systems = await self._async_get_systems(reauth_entry.data | user_input)
            except ValueError, RedfishAuthError:
                errors["base"] = "invalid_auth"
            except RedfishError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception validating Redfish service")
                errors["base"] = "unknown"
            else:
                if not systems:
                    errors["base"] = "no_systems"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                {
                    CONF_USERNAME: (
                        user_input[CONF_USERNAME]
                        if user_input is not None
                        else reauth_entry.data[CONF_USERNAME]
                    )
                },
            ),
            errors=errors,
        )
