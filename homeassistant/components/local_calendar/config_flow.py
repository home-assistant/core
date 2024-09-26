"""Config flow for Local Calendar integration."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import (
    CONF_CALENDAR_NAME,
    CONF_CALENDAR_URL,
    CONF_STORAGE_KEY,
    CONF_SYNC_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Optional(CONF_CALENDAR_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_SYNC_INTERVAL): DurationSelector(
            DurationSelectorConfig(
                enable_day=True, enable_millisecond=False, allow_negative=False
            )
        ),
    }
)


class LocalCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local Calendar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        key = slugify(user_input[CONF_CALENDAR_NAME])
        self._async_abort_entries_match({CONF_STORAGE_KEY: key})
        user_input[CONF_STORAGE_KEY] = key
        if url := user_input.get(CONF_CALENDAR_URL):
            try:
                vol.Schema(vol.Url())(url)
            except vol.Invalid:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(
                        data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
                    ),
                    errors={CONF_CALENDAR_URL: "invalid_url"},
                    last_step=True,
                )
            client = get_async_client(self.hass)
            res = await client.get(url)
            try:
                res.raise_for_status()
            except httpx.HTTPError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self.add_suggested_values_to_schema(
                        data_schema=STEP_USER_DATA_SCHEMA, suggested_values=user_input
                    ),
                    errors={CONF_CALENDAR_URL: "cannot_connect"},
                    last_step=True,
                )
        return self.async_create_entry(
            title=user_input[CONF_CALENDAR_NAME], data=user_input
        )
