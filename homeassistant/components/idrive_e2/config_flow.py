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
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
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
        vol.Required(CONF_SECRET_ACCESS_KEY): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
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

    _data: dict[str, str]
    _buckets: list[str]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: prompt for access_key and secret_access_key, then fetch region endpoint and buckets."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = IDriveE2Client(session)

            try:
                endpoint = await client.get_region_endpoint(
                    user_input[CONF_ACCESS_KEY_ID]
                )
                # Get the list of buckets belonging to the provided credentials
                buckets = await _list_buckets(
                    endpoint,
                    user_input[CONF_ACCESS_KEY_ID],
                    user_input[CONF_SECRET_ACCESS_KEY],
                )
            except InvalidAuth, ClientError:
                errors["base"] = "invalid_credentials"
            except CannotConnect, ConnectionError:
                errors["base"] = "cannot_connect"
            except ValueError:
                errors["base"] = "invalid_endpoint_url"
            else:
                # Check if any buckets were found
                if not buckets:
                    errors["base"] = "no_buckets"

            if not errors:
                # Store validated data for the next step
                self._data = {
                    CONF_ACCESS_KEY_ID: user_input[CONF_ACCESS_KEY_ID],
                    CONF_SECRET_ACCESS_KEY: user_input[CONF_SECRET_ACCESS_KEY],
                    CONF_ENDPOINT_URL: endpoint,
                }
                self._buckets = buckets
                return await self.async_step_bucket()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_bucket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: list preloaded buckets and let user select from dropdown."""
        if user_input is not None:
            # Check if the entry already exists to avoid duplicates
            self._async_abort_entries_match(
                {
                    CONF_BUCKET: user_input[CONF_BUCKET],
                    CONF_ENDPOINT_URL: self._data[CONF_ENDPOINT_URL],
                }
            )

            return self.async_create_entry(
                title=user_input[CONF_BUCKET],
                data={**self._data, CONF_BUCKET: user_input[CONF_BUCKET]},
            )

        # Show the bucket selection form with a dropdown selector
        return self.async_show_form(
            step_id="bucket",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BUCKET): SelectSelector(
                        config=SelectSelectorConfig(
                            options=self._buckets, mode=SelectSelectorMode.DROPDOWN
                        )
                    )
                }
            ),
        )
