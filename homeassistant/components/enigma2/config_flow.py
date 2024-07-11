"""Config flow for Enigma2."""

from typing import Any, cast

from aiohttp.client_exceptions import ClientError
from openwebif.api import OpenWebIfDevice
from openwebif.error import InvalidAuthError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import (
    CONF_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): selector.TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
        ),
        vol.Optional(CONF_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_SSL, default=DEFAULT_SSL): selector.BooleanSelector(),
        vol.Required(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
    }
)


async def get_options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Get the options schema."""
    entry = cast(SchemaOptionsFlowHandler, handler.parent_handler).config_entry
    device: OpenWebIfDevice = entry.runtime_data
    bouquets = [b[1] for b in (await device.get_all_bouquets())["bouquets"]]

    return vol.Schema(
        {
            vol.Optional(CONF_DEEP_STANDBY): selector.BooleanSelector(),
            vol.Optional(CONF_SOURCE_BOUQUET): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=bouquets,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_USE_CHANNEL_ICON): selector.BooleanSelector(),
        }
    )


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(get_options_schema),
}


class Enigma2ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Enigma2."""

    DATA_KEYS = (
        CONF_HOST,
        CONF_PORT,
        CONF_USERNAME,
        CONF_PASSWORD,
        CONF_SSL,
        CONF_VERIFY_SSL,
    )
    OPTIONS_KEYS = (CONF_DEEP_STANDBY, CONF_SOURCE_BOUQUET, CONF_USE_CHANNEL_ICON)

    async def validate_user_input(
        self, user_input: dict[str, Any]
    ) -> dict[str, str] | None:
        """Validate user input."""

        errors = None

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        base_url = URL.build(
            scheme="http" if not user_input[CONF_SSL] else "https",
            host=user_input[CONF_HOST],
            port=user_input[CONF_PORT],
            user=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
        )

        session = async_create_clientsession(
            self.hass, verify_ssl=user_input[CONF_VERIFY_SSL], base_url=base_url
        )

        try:
            about = await OpenWebIfDevice(session).get_about()
        except InvalidAuthError:
            errors = {"base": "invalid_auth"}
        except ClientError:
            errors = {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            errors = {"base": "unknown"}
        else:
            await self.async_set_unique_id(about["info"]["ifaces"][0]["mac"])
            self._abort_if_unique_id_configured()

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(step_id=SOURCE_USER, data_schema=CONFIG_SCHEMA)

        if errors := await self.validate_user_input(user_input):
            return self.async_show_form(
                step_id=SOURCE_USER, data_schema=CONFIG_SCHEMA, errors=errors
            )
        return self.async_create_entry(data=user_input, title=user_input[CONF_HOST])

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the import step."""
        if CONF_PORT not in user_input:
            user_input[CONF_PORT] = DEFAULT_PORT
        if CONF_SSL not in user_input:
            user_input[CONF_SSL] = DEFAULT_SSL
        user_input[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL

        data = {key: user_input[key] for key in user_input if key in self.DATA_KEYS}
        options = {
            key: user_input[key] for key in user_input if key in self.OPTIONS_KEYS
        }

        if errors := await self.validate_user_input(user_input):
            async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_yaml_{DOMAIN}_import_issue_{errors["base"]}",
                breaks_in_ha_version="2024.11.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key=f"deprecated_yaml_import_issue_{errors["base"]}",
                translation_placeholders={
                    "url": "/config/integrations/dashboard/add?domain=enigma2"
                },
            )
            return self.async_abort(reason=errors["base"])

        async_create_issue(
            self.hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.11.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Enigma2",
            },
        )
        return self.async_create_entry(
            data=data, title=data[CONF_HOST], options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
