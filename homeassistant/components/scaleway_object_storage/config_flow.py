"""Config flow for the Scaleway Object Storage integration."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import exceptions, helpers
from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    CONF_REGION,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
    DOCS_PLACEHOLDERS,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigFlowResult

SECTION_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SECTION_CREDENTIALS): section(SECTION_CREDENTIALS_SCHEMA),
        vol.Required(CONF_REGION, default="fr-par"): SelectSelector(
            SelectSelectorConfig(
                translation_key="regions",
                options=[
                    "fr-par",
                    "nl-ams",
                    "pl-waw",
                    "it-mil",
                ],
            )
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Optional(CONF_OBJECT_PREFIX, default=""): cv.string,
    }
)


class ScalewayConfigFlow(ConfigFlow, domain=DOMAIN):
    """ConfigFlow for the Scaleway Object Storage integration."""

    VERSION = 1

    @staticmethod
    def _generate_title(config: Mapping[str, Any]) -> str:
        prefix = config.get(CONF_OBJECT_PREFIX, "")
        bucket_name = config[CONF_BUCKET]
        region = config[CONF_REGION]

        if prefix:
            base_name = f"{bucket_name}/{prefix}"
        else:
            base_name = bucket_name

        return f"{base_name} ({region})"

    @staticmethod
    def _get_uniqueness_markers(config: Mapping[str, Any]) -> dict[str, Any]:
        return {
            CONF_REGION: config[CONF_REGION],
            CONF_BUCKET: config[CONF_BUCKET],
            CONF_OBJECT_PREFIX: config[CONF_OBJECT_PREFIX],
        }

    async def _test_connection(
        self,
        *,
        errors: dict[str, str],
        config: dict[str, Any],
    ) -> bool:
        """Tests the connection to Scaleway using the given config.

        Args:
            errors: if any errors are detected, they'll be added to this dict
            config: the current configuration to test

        Returns:
            True, if the connection succeeded.
        """
        session = async_get_clientsession(self.hass)
        client = helpers.create_client(session, config)
        try:
            await helpers.check_connection(client)
        except exceptions.ScalewayConfigException as e:
            errors[e.config_schema_key] = e.config_translation_key
            return False
        else:
            return True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(self._get_uniqueness_markers(user_input))

            if await self._test_connection(errors=errors, config=user_input):
                return self.async_create_entry(
                    title=self._generate_title(user_input),
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            description_placeholders=DOCS_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_data is not None:
            self._async_abort_entries_match(self._get_uniqueness_markers(user_data))

            if await self._test_connection(errors=errors, config=user_data):
                return self.async_update_reload_and_abort(
                    entry,
                    data=user_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_data or entry.data,
            ),
            description_placeholders=DOCS_PLACEHOLDERS,
            errors=errors,
        )
