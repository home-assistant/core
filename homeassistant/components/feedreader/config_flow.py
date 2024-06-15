"""Config flow for RSS/Atom feeds."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
import urllib.error

import feedparser
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_MAX_ENTRIES, DEFAULT_MAX_ENTRIES, DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_fetch_feed(hass: HomeAssistant, url: str) -> feedparser.FeedParserDict:
    """Fetch the feed."""
    return await hass.async_add_executor_job(feedparser.parse, url)


class FeedReaderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    _config_entry: ConfigEntry

    def show_user_form(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, str] | None = None,
        step_id: str = "user",
    ) -> ConfigFlowResult:
        """Show the user form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL, default=user_input.get(CONF_URL, "")
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                    vol.Optional(
                        CONF_MAX_ENTRIES,
                        default=user_input.get(CONF_MAX_ENTRIES, DEFAULT_MAX_ENTRIES),
                    ): cv.positive_int,
                },
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if not user_input:
            return self.show_user_form()

        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})

        feed = await async_fetch_feed(self.hass, user_input[CONF_URL])

        if feed.bozo:
            LOGGER.debug("feed bozo_exception: %s", feed.bozo_exception)
            if isinstance(feed.bozo_exception, urllib.error.URLError):
                return self.show_user_form(user_input, {"base": "url_error"})

        if not feed.entries:
            return self.show_user_form(user_input, {"base": "no_feed_entries"})

        feed_title = feed["feed"]["title"]

        return self.async_create_entry(title=feed_title, data=user_input)

    async def async_step_import(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an import flow."""
        return await self.async_step_user(user_input)

    async def async_step_reconfigure(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if TYPE_CHECKING:
            assert config_entry is not None
        self._config_entry = config_entry
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        if not user_input:
            return self.show_user_form(
                user_input={**self._config_entry.data},
                description_placeholders={"name": self._config_entry.title},
                step_id="reconfigure_confirm",
            )

        feed = await async_fetch_feed(self.hass, user_input[CONF_URL])

        if feed.bozo:
            LOGGER.debug("feed bozo_exception: %s", feed.bozo_exception)
            if isinstance(feed.bozo_exception, urllib.error.URLError):
                return self.show_user_form(
                    user_input=user_input,
                    description_placeholders={"name": self._config_entry.title},
                    step_id="reconfigure_confirm",
                    errors={"base": "url_error"},
                )
        if not feed.entries:
            return self.show_user_form(
                user_input=user_input,
                description_placeholders={"name": self._config_entry.title},
                step_id="reconfigure_confirm",
                errors={"base": "no_feed_entries"},
            )

        self.hass.config_entries.async_update_entry(self._config_entry, data=user_input)
        return self.async_abort(reason="reconfigure_successful")
