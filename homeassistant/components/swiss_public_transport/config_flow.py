"""Config flow for transport.opendata.ch."""
from typing import Any, Optional

from opendata_transport import OpendataTransport
from opendata_transport.exceptions import OpendataTransportError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import CONF_DESTINATION, CONF_START, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_START): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
    }
)


class SwissPublicTransportConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Swiss public transport config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Async user step to set up the connection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            opendata = OpendataTransport(
                user_input[CONF_START], user_input[CONF_DESTINATION], session
            )
            try:
                await opendata.async_get_data()
            except OpendataTransportError:
                errors["base"] = "client"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{user_input[CONF_START]} {user_input[CONF_DESTINATION]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_input: dict[str, Any]) -> FlowResult:
        """Async import step to set up the connection."""
        await self.async_set_unique_id(import_input[CONF_NAME])
        try:
            self._abort_if_unique_id_configured()
        except AbortFlow as err:
            async_create_issue(
                self.hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": DOMAIN,
                },
            )
            raise err
        try:
            session = async_get_clientsession(self.hass)
            opendata = OpendataTransport(
                import_input[CONF_START], import_input[CONF_DESTINATION], session
            )
            await opendata.async_get_data()
        except OpendataTransportError:
            async_create_issue(
                self.hass,
                DOMAIN,
                "deprecated_yaml_import_issue_client",
                breaks_in_ha_version="2024.7.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_yaml_import_issue_client",
            )
            return self.async_abort(reason="client")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown")

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": DOMAIN,
            },
        )
        return self.async_create_entry(
            title=import_input[CONF_NAME],
            data=import_input,
        )
