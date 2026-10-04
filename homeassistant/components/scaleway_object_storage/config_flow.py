"""Config flow for the Scaleway Object Storage integration."""

from collections.abc import Mapping
from typing import Any, Final, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
    DOMAIN,
)

DOCS_PLACEHOLDERS: Final = {
    "api_key_docs": "https://www.scaleway.com/docs/iam/api-cli/using-api-key-object-storage/",
    "bucket_docs": "https://www.scaleway.com/docs/object-storage/how-to/create-a-bucket/",
}


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
        vol.Required(CONF_BUCKET): vol.All(
            cv.string,
            vol.Length(max=63),
            # See https://www.scaleway.com/en/docs/object-storage/faq/#is-there-a-limitation-on-the-bucket-name
            cv.matches_regex(r"^[a-z\d\-.]+$"),
        ),
        vol.Optional(CONF_OBJECT_PREFIX, default=""): cv.string,
    }
)


class ScalewayConfigFlow(ConfigFlow, domain=DOMAIN):
    """ConfigFlow for the Scaleway Object Storage integration."""

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

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_REGION: user_input[CONF_REGION],
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_OBJECT_PREFIX: user_input[CONF_OBJECT_PREFIX],
                }
            )

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
