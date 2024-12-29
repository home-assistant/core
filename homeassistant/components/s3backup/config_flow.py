"""Config flow to configure the S3 Cloud Storage integration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
import botocore.client
from botocore.exceptions import ClientError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_ACCESS_KEY, CONF_BUCKET, CONF_S3_URL, CONF_SECRET_KEY, DOMAIN


@dataclass(kw_only=True)
class Bucket:
    """Representation of a S3 bucket."""

    def __init__(self, name: str, creation_date: datetime) -> None:
        """Initialize the bucket."""
        self.name = name
        self.creation_date = creation_date

    def __repr__(self):
        """Return the representation of the bucket."""
        return f"Bucket(name={self.name}, creation_date={self.creation_date})"


def get_buckets(client: botocore.client.S3) -> list[Bucket]:
    """Retrieve the list of buckets (for mock testing)."""
    response = client.list_buckets()
    return [
        Bucket(bucket["Name"], bucket["CreationDate"]) for bucket in response["Buckets"]
    ]


class S3FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a S3 config flow."""

    VERSION = 1

    _buckets: Sequence[Bucket]
    _authorization: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # LOGGER.info("Yeah, we're in the user step: %s", user_input)
        errors = {}

        if user_input is not None:
            # Create a session using your credentials
            # LOGGER.info("Creating a session using the provided credentials")
            session = boto3.Session(
                aws_access_key_id=user_input.get(CONF_ACCESS_KEY),
                aws_secret_access_key=user_input.get(CONF_SECRET_KEY),
            )

            try:
                # Create an S3 client
                # LOGGER.info("Creating an S3 client")
                s3_client = await self.hass.async_add_executor_job(
                    session.client,
                    "s3",
                    None,
                    None,
                    True,
                    None,
                    user_input.get(CONF_S3_URL),
                )
                # Retrieve the list of buckets
                # LOGGER.info("Retrieving the list of buckets")
                response = await self.hass.async_add_executor_job(
                    get_buckets, s3_client
                )
                # LOGGER.info("Response: %s", response)
                self._buckets = response
                # LOGGER.info("Buckets: %s", self._buckets)
            except ValueError as e:
                # LOGGER.info("ValueError: %s", e)
                error_message = str(e)
                errors["base"] = error_message
            except ClientError as e:
                # LOGGER.info("ClientError: %s", e)
                error_message = str(e)
                errors["base"] = error_message
            except Exception as e:  # noqa: BLE001
                # LOGGER.info("Exception: %s", e)
                error_message = str(e)
                if error_message in (None, ""):
                    errors["base"] = "unknown"
                else:
                    errors["base"] = error_message
            else:
                # LOGGER.info("No errors")
                self._authorization = user_input
                return await self.async_step_bucket()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ACCESS_KEY,
                        default=user_input.get(CONF_ACCESS_KEY),
                    ): TextSelector(
                        config=TextSelectorConfig(
                            autocomplete="off",
                        ),
                    ),
                    vol.Required(CONF_SECRET_KEY): TextSelector(
                        config=TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Required(
                        CONF_S3_URL,
                        default=user_input.get(CONF_S3_URL),
                    ): TextSelector(
                        config=TextSelectorConfig(
                            autocomplete="off",
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_bucket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a bucket selection."""
        # LOGGER.info("Yeah, we're in the bucket step: %s", user_input)
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_BUCKET])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=(
                    next(
                        bucket.name
                        for bucket in self._buckets
                        if bucket.name == user_input[CONF_BUCKET]
                    )
                    or "S3"
                ),
                data=self._authorization | user_input,
            )

        # LOGGER.info("Buckets: %s", self._buckets)
        return self.async_show_form(
            step_id="bucket",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BUCKET,
                    ): SelectSelector(
                        config=SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN,
                            options=[
                                SelectOptionDict(
                                    value=bucket.name,
                                    label=bucket.name,
                                )
                                for bucket in self._buckets
                            ],
                            sort=True,
                        )
                    ),
                }
            ),
        )
