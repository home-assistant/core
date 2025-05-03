"""Config flow for the S3 integration."""

from __future__ import annotations

import logging
from typing import Any
import uuid

from aiobotocore.session import AioSession
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectionError, ParamValidationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_CHECKSUM_MODE,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_ENDPOINT_URL,
    DESCRIPTION_AWS_S3_DOCS_URL,
    DESCRIPTION_BOTO3_DOCS_URL,
    DOMAIN,
    ChecksumMode,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_BUCKET): cv.string,
        vol.Required(CONF_ENDPOINT_URL, default=DEFAULT_ENDPOINT_URL): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.URL)
        ),
    }
)


_LOGGER = logging.getLogger(__name__)


async def _detect_checksum_mode(client: AioSession, bucket_name: str) -> ChecksumMode:
    """Detect the checksum mode to use by performing a test write.

    Return the checksum mode to use based on the success/failure of the test write.
    """
    key = f"homeassistant_test_{uuid.uuid4().hex}.tmp"
    try:
        await client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=b"",
        )
        await client.delete_object(
            Bucket=bucket_name,
            Key=key,
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        error_msg = error.get("Message", "") or ""  # Message can be None
        error_code = error.get("Code", "") or ""
        if any(
            (
                # https://github.com/home-assistant/core/issues/143995
                "Unsupported header 'x-amz-sdk-checksum-algorithm'" in error_msg,
                # https://github.com/home-assistant/core/issues/144015
                "XAmzContentSHA256Mismatch" in error_code,
            )
        ):
            _LOGGER.info("Test write failed, using 'when_required' checksum mode")
            _LOGGER.debug("Test write error: %s", error)
            return ChecksumMode.WHEN_REQUIRED
        raise  # re-raise any other ClientErrors as they are not related to checksum mode
    _LOGGER.info("Test write succeeded, using 'when_supported' checksum mode")
    return ChecksumMode.WHEN_SUPPORTED


class S3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            bucket = user_input[CONF_BUCKET]
            endpoint_url = user_input[CONF_ENDPOINT_URL]
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: bucket,
                    CONF_ENDPOINT_URL: endpoint_url,
                }
            )
            # we need to start with ChecksumMode.WHEN_SUPPORTED to let _detect_checksum_mode detect possible failure
            config = Config(
                request_checksum_calculation=ChecksumMode.WHEN_SUPPORTED,
                response_checksum_validation=ChecksumMode.WHEN_SUPPORTED,
            )
            try:
                session = AioSession()
                async with session.create_client(
                    "s3",
                    endpoint_url=endpoint_url,
                    aws_secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
                    aws_access_key_id=user_input[CONF_ACCESS_KEY_ID],
                    config=config,
                ) as client:
                    await client.head_bucket(Bucket=bucket)
                    checksum_mode = await _detect_checksum_mode(client, bucket)

            except ClientError:
                errors["base"] = "invalid_credentials"
            except ParamValidationError as err:
                if "Invalid bucket name" in str(err):
                    errors[CONF_BUCKET] = "invalid_bucket_name"
            except ValueError:
                errors[CONF_ENDPOINT_URL] = "invalid_endpoint_url"
            except ConnectionError:
                errors[CONF_ENDPOINT_URL] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_BUCKET],
                    data={
                        **user_input,
                        CONF_CHECKSUM_MODE: checksum_mode,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "aws_s3_docs_url": DESCRIPTION_AWS_S3_DOCS_URL,
                "boto3_docs_url": DESCRIPTION_BOTO3_DOCS_URL,
            },
        )
