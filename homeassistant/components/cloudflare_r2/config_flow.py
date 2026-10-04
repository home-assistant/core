"""Config flow for the Cloudflare R2 integration."""

from collections.abc import Mapping
import logging
from typing import Any, override
from urllib.parse import urlparse

from aiobotocore.config import AioConfig
from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PREFIX
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    AUTH_ERROR_HTTP_STATUS_CODES,
    BUCKET_NOT_FOUND_ERROR_CODES,
    CLOUDFLARE_R2_DOMAIN,
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_ENDPOINT_URL,
    DESCRIPTION_R2_AUTH_DOCS_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ACCESS_KEY_ID): cv.string,
        probatio.Required(probatio.Secret(CONF_SECRET_ACCESS_KEY)): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        probatio.Required(CONF_BUCKET): cv.string,
        probatio.Required(
            CONF_ENDPOINT_URL, default=DEFAULT_ENDPOINT_URL
        ): TextSelector(config=TextSelectorConfig(type=TextSelectorType.URL)),
        probatio.Optional(CONF_PREFIX, default=""): cv.string,
    }
)


STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ACCESS_KEY_ID): cv.string,
        probatio.Required(probatio.Secret(CONF_SECRET_ACCESS_KEY)): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _async_validate_input(data: Mapping[str, Any]) -> dict[str, str]:
    """Validate the endpoint and that the bucket is accessible."""
    parsed = urlparse(data[CONF_ENDPOINT_URL])
    if not parsed.hostname or not parsed.hostname.endswith(CLOUDFLARE_R2_DOMAIN):
        return {CONF_ENDPOINT_URL: "invalid_endpoint_url"}
    try:
        session = AioSession()
        async with session.create_client(
            "s3",
            endpoint_url=data[CONF_ENDPOINT_URL],
            aws_secret_access_key=data[CONF_SECRET_ACCESS_KEY],
            aws_access_key_id=data[CONF_ACCESS_KEY_ID],
            config=AioConfig(warm_up_loader_caches=True),
        ) as client:
            await client.head_bucket(Bucket=data[CONF_BUCKET])
    except ClientError as err:
        if err.response["Error"]["Code"] in BUCKET_NOT_FOUND_ERROR_CODES:
            return {CONF_BUCKET: "bucket_not_found"}
        if (
            err.response["ResponseMetadata"]["HTTPStatusCode"]
            in AUTH_ERROR_HTTP_STATUS_CODES
        ):
            return {"base": "invalid_credentials"}
        return {"base": "service_error"}
    except ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            return {CONF_BUCKET: "invalid_bucket_name"}
        _LOGGER.exception("Unexpected parameter validation error")
        return {"base": "unknown"}
    except ValueError:
        return {CONF_ENDPOINT_URL: "invalid_endpoint_url"}
    except EndpointConnectionError, ConnectionError:
        return {CONF_ENDPOINT_URL: "cannot_connect"}
    return {}


def _entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return entry data without empty optional values."""
    data = dict(user_input)
    if not data.get(CONF_PREFIX):
        data.pop(CONF_PREFIX, None)
    return data


class R2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cloudflare R2."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_ENDPOINT_URL: user_input[CONF_ENDPOINT_URL],
                }
            )

            errors = await _async_validate_input(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET], data=_entry_data(user_input)
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "auth_docs_url": DESCRIPTION_R2_AUTH_DOCS_URL,
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored credentials are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            validation_errors = await _async_validate_input(
                reauth_entry.data | user_input
            )
            if not validation_errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )
            # Endpoint and bucket are not on this form, so show errors as base
            errors["base"] = next(iter(validation_errors.values()))

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                user_input
                or {CONF_ACCESS_KEY_ID: reauth_entry.data[CONF_ACCESS_KEY_ID]},
            ),
            errors=errors,
            description_placeholders={
                "name": reauth_entry.title,
                "auth_docs_url": DESCRIPTION_R2_AUTH_DOCS_URL,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_ENDPOINT_URL: user_input[CONF_ENDPOINT_URL],
                }
            )

            errors = await _async_validate_input(user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=user_input[CONF_BUCKET],
                    data=_entry_data(user_input),
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or reconfigure_entry.data
            ),
            errors=errors,
            description_placeholders={
                "auth_docs_url": DESCRIPTION_R2_AUTH_DOCS_URL,
            },
        )
