"""IDrive e2 config flow."""

from __future__ import annotations

import logging
from typing import Any, cast

from aiobotocore.session import AioSession
from botocore.exceptions import ClientError, ConnectionError
from idrive_e2 import CannotConnect, IDriveE2Client, InvalidAuth
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_SECRET_ACCESS_KEY): cv.string,
    }
)


async def _list_buckets(
    endpoint_url: str, access_key: str, secret_key: str
) -> list[str]:
    """List S3 buckets."""
    session = AioSession()
    async with session.create_client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    ) as client:
        result = await cast(Any, client).list_buckets()

    return [bucket["Name"] for bucket in result.get("Buckets", []) if "Name" in bucket]


class IDriveE2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IDrive e2."""

    _access_key: str
    _secret_key: str
    _endpoint_url: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: prompt for access_key and secret_access_key, then fetch region endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = IDriveE2Client(session)
            try:
                endpoint = await client.get_region_endpoint(
                    user_input[CONF_ACCESS_KEY_ID]
                )
            except InvalidAuth:
                errors["base"] = "invalid_credentials"
            except CannotConnect:
                errors["base"] = "cannot_connect"

            if not errors:
                # Process to the next step (select bucket)
                self._access_key = user_input[CONF_ACCESS_KEY_ID]
                self._secret_key = user_input[CONF_SECRET_ACCESS_KEY]
                self._endpoint_url = endpoint
                return await self.async_step_bucket()

            # Show the userform with the entered data and errors
            # Prefill the access key and secret key fields with the previous values
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_bucket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: list buckets and let user select from dropdown."""
        errors: dict[str, str] = {}

        # Make sure that the bucket step is only executed after
        # the endpoint_url is determined in the user step
        if not hasattr(self, "_endpoint_url"):
            return await self.async_step_user()

        if user_input:
            # Check if the entry already exists to avoid duplicates
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_ENDPOINT_URL: self._endpoint_url,
                }
            )

            return self.async_create_entry(
                title=user_input[CONF_BUCKET],
                data={
                    CONF_ACCESS_KEY_ID: self._access_key,
                    CONF_SECRET_ACCESS_KEY: self._secret_key,
                    CONF_ENDPOINT_URL: self._endpoint_url,
                    CONF_BUCKET: user_input[CONF_BUCKET],
                },
            )

        # Information should be available from the previous step
        try:
            # List buckets using the provided credentials
            buckets = await _list_buckets(
                self._endpoint_url,
                self._access_key,
                self._secret_key,
            )
        except ClientError:
            errors["base"] = "invalid_credentials"
        except ValueError:
            errors["base"] = "invalid_endpoint_url"
        except ConnectionError:
            errors["base"] = "cannot_connect"

        if errors:
            # Go back to the user step if there are errors getting buckets
            # Prefill the access key and secret key fields with the current values
            suggested = {
                CONF_ACCESS_KEY_ID: self._access_key,
                CONF_SECRET_ACCESS_KEY: self._secret_key,
            }
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, suggested
                ),
                errors=errors,
            )

        # Show the bucket selection form with a dropdown selector
        return self.async_show_form(
            step_id="bucket",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUCKET): SelectSelector(
                        config=SelectSelectorConfig(
                            options=buckets, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )
