"""Config flow for the AWS S3 integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .config_model import S3ConfigModel
from .const import (
    AWS_DOMAIN,
    CONF_ACCESS_KEY_ID,
    CONF_AUTH_MODE,
    CONF_AUTH_MODE_EXPLICIT,
    CONF_AUTH_MODE_IMPLICIT,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_ENDPOINT_URL,
    DESCRIPTION_AWS_S3_DOCS_URL,
    DESCRIPTION_BOTO3_CREDS_URL,
    DESCRIPTION_BOTO3_DOCS_URL,
    DOMAIN,
)

STEP_BUCKET_DATA_VALUES = {
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_AUTH_MODE,
}

STEP_BUCKET_CREATE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BUCKET): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_ENDPOINT_URL, default=DEFAULT_ENDPOINT_URL): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_AUTH_MODE): SelectSelector(
            SelectSelectorConfig(
                options=[
                    CONF_AUTH_MODE_IMPLICIT,
                    CONF_AUTH_MODE_EXPLICIT,
                ],
                mode=SelectSelectorMode.LIST,
                multiple=False,
                translation_key="auth_mode",
            )
        ),
    }
)

STEP_EXPLICIT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.TEXT)
        ),
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class S3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    _config_models: dict[str, S3ConfigModel] = {}

    def _model(self) -> S3ConfigModel:
        if self.flow_id not in S3ConfigFlow._config_models:
            S3ConfigFlow._config_models[self.flow_id] = S3ConfigModel()
        return S3ConfigFlow._config_models[self.flow_id]

    def async_remove(self):
        """Handle the notification that the flow has been removed."""
        if self.flow_id in S3ConfigFlow._config_models:
            del S3ConfigFlow._config_models[self.flow_id]

    async def async_step_user(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial flow initiated by the user."""
        self._model()
        return await self.async_step_bucket()

    async def async_step_bucket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the bucket selection and authentication mode step in the config flow."""
        model = self._model()

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input.get(CONF_BUCKET),
                }
            )

            if not urlparse(user_input[CONF_ENDPOINT_URL]).hostname.endswith(
                AWS_DOMAIN
            ):
                model.record_error(CONF_ENDPOINT_URL, "invalid_endpoint_url")
            else:
                model.from_dict(user_input)
                if model[CONF_AUTH_MODE] == CONF_AUTH_MODE_IMPLICIT:
                    await model.async_validate_access()

        if (errors := model.get_errors()) or user_input is None:
            return self.async_show_form(
                step_id="bucket",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_BUCKET_CREATE_DATA_SCHEMA,
                    user_input,
                ),
                errors=errors,
                description_placeholders={
                    "aws_s3_docs_url": DESCRIPTION_AWS_S3_DOCS_URL,
                    "boto3_docs_url": DESCRIPTION_BOTO3_DOCS_URL,
                    "boto3_creds_url": DESCRIPTION_BOTO3_CREDS_URL,
                },
            )

        if model[CONF_AUTH_MODE] == CONF_AUTH_MODE_EXPLICIT:
            return await self.async_step_explicit()

        # Assume model[CONF_AUTH_MODE] == CONF_AUTH_MODE_IMPLICIT:
        return self.async_create_entry(
            title=user_input[CONF_BUCKET],
            data=model.as_dict(),
        )

    async def async_step_explicit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the explicit credentials auth flow."""

        model = self._model()

        if (
            user_input is not None
            and user_input.get(CONF_ACCESS_KEY_ID)
            and user_input.get(CONF_SECRET_ACCESS_KEY)
        ):
            model.from_dict(user_input)
            await model.async_validate_access()
            if model.has_errors(STEP_BUCKET_DATA_VALUES):
                # These errors must be handled by the bucket step, not the auth step
                model.filter_errors(STEP_BUCKET_DATA_VALUES)
                return await self.async_step_bucket(
                    model.as_dict(STEP_BUCKET_DATA_VALUES)
                )

        if (errors := model.get_errors()) or (
            user_input is None
            or user_input.get(CONF_ACCESS_KEY_ID) is None
            or user_input.get(CONF_SECRET_ACCESS_KEY) is None
        ):
            return self.async_show_form(
                step_id="explicit",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_EXPLICIT_DATA_SCHEMA, user_input
                ),
                errors=errors,
            )

        return self.async_create_entry(title=model[CONF_BUCKET], data=model.as_dict())
