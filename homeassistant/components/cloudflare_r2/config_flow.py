"""Config flow for the Cloudflare R2 integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CLOUDFLARE_R2_DOMAIN,
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_ENDPOINT_URL,
    DESCRIPTION_R2_AUTH_DOCS_URL,
    DOMAIN,
)

S3_API_VERSION = "2006-03-01"


def _preload_botocore_data(session: AioSession) -> None:
    """Pre-load botocore S3 data to avoid blocking the event loop.

    botocore performs synchronous file I/O (os.listdir, gzip.open) when loading
    service model data during client creation. Pre-loading the data into the
    session's internal loader cache avoids these blocking calls.
    """
    loader = session.get_component("data_loader")
    loader.load_service_model("s3", "service-2", S3_API_VERSION)
    loader.load_service_model("s3", "endpoint-rule-set-1", S3_API_VERSION)
    loader.load_data("partitions")
    loader.load_data("sdk-default-configuration")


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
        vol.Optional(CONF_PREFIX, default=""): cv.string,
    }
)


class R2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cloudflare R2."""

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

            parsed = urlparse(user_input[CONF_ENDPOINT_URL])
            if not parsed.hostname or not parsed.hostname.endswith(
                CLOUDFLARE_R2_DOMAIN
            ):
                errors[CONF_ENDPOINT_URL] = "invalid_endpoint_url"
            else:
                try:
                    session = AioSession()
                    await self.hass.async_add_executor_job(
                        _preload_botocore_data, session
                    )
                    async with session.create_client(
                        "s3",
                        endpoint_url=user_input.get(CONF_ENDPOINT_URL),
                        aws_secret_access_key=user_input[CONF_SECRET_ACCESS_KEY],
                        aws_access_key_id=user_input[CONF_ACCESS_KEY_ID],
                        api_version=S3_API_VERSION,
                    ) as client:
                        await client.head_bucket(Bucket=user_input[CONF_BUCKET])
                except ClientError:
                    errors["base"] = "invalid_credentials"
                except ParamValidationError as err:
                    if "Invalid bucket name" in str(err):
                        errors[CONF_BUCKET] = "invalid_bucket_name"
                except ValueError:
                    errors[CONF_ENDPOINT_URL] = "invalid_endpoint_url"
                except EndpointConnectionError:
                    errors[CONF_ENDPOINT_URL] = "cannot_connect"
                except ConnectionError:
                    errors[CONF_ENDPOINT_URL] = "cannot_connect"
                else:
                    # Do not persist empty optional values
                    data = dict(user_input)
                    if not data.get(CONF_PREFIX):
                        data.pop(CONF_PREFIX, None)
                    return self.async_create_entry(
                        title=user_input[CONF_BUCKET], data=data
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
