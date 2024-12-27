"""Config flow to configure the Backblaze B2 Cloud Storage integration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from b2sdk.v2 import AuthInfoCache, B2Api, Bucket, InMemoryAccountInfo
from b2sdk.v2.exception import InvalidAuthToken
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

from .const import (
    CONF_APPLICATION_KEY,
    CONF_APPLICATION_KEY_ID,
    CONF_BUCKET,
    DOMAIN,
    LOGGER,
)


class BackblazeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Backblaze config flow."""

    VERSION = 1

    _buckets: Sequence[Bucket]
    _authorization: dict[str, Any]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            info = InMemoryAccountInfo()
            backblaze = B2Api(info, cache=AuthInfoCache(info))
            try:
                await self.hass.async_add_executor_job(
                    backblaze.authorize_account,
                    "production",
                    user_input[CONF_APPLICATION_KEY_ID],
                    user_input[CONF_APPLICATION_KEY],
                )
                self._buckets = await self.hass.async_add_executor_job(
                    backblaze.list_buckets,
                )
            except InvalidAuthToken:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._authorization = user_input
                return await self.async_step_bucket()
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APPLICATION_KEY_ID,
                        default=user_input.get(CONF_APPLICATION_KEY_ID),
                    ): TextSelector(
                        config=TextSelectorConfig(
                            autocomplete="off",
                        ),
                    ),
                    vol.Required(CONF_APPLICATION_KEY): TextSelector(
                        config=TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
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
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_BUCKET])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=(
                    next(
                        bucket.name
                        for bucket in self._buckets
                        if bucket.id_ == user_input[CONF_BUCKET]
                    )
                    or "Backblaze"
                ),
                data=self._authorization | user_input,
            )

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
                                    value=bucket.id_,
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
