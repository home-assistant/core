"""Config flow for RSS/Atom feeds."""

from __future__ import annotations

import html
import logging
from typing import Any
import urllib.error

import feedparser
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import CONF_MAX_ENTRIES, DEFAULT_MAX_ENTRIES, DOMAIN

LOGGER = logging.getLogger(__name__)


async def async_fetch_feed(hass: HomeAssistant, url: str) -> feedparser.FeedParserDict:
    """Fetch the feed."""
    return await hass.async_add_executor_job(feedparser.parse, url)


class FeedReaderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    _max_entries: int | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for this handler."""
        return FeedReaderOptionsFlowHandler()

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
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
                }
            ),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    def abort_on_import_error(self, url: str, error: str) -> ConfigFlowResult:
        """Abort import flow on error."""
        async_create_issue(
            self.hass,
            DOMAIN,
            f"import_yaml_error_{DOMAIN}_{error}_{slugify(url)}",
            breaks_in_ha_version="2025.1.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"import_yaml_error_{error}",
            translation_placeholders={"url": url},
        )
        return self.async_abort(reason=error)

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
                if self.context["source"] == SOURCE_IMPORT:
                    return self.abort_on_import_error(user_input[CONF_URL], "url_error")
                return self.show_user_form(user_input, {"base": "url_error"})

        feed_title = html.unescape(feed["feed"]["title"])

        return self.async_create_entry(
            title=feed_title,
            data=user_input,
            options={CONF_MAX_ENTRIES: self._max_entries or DEFAULT_MAX_ENTRIES},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle an import flow."""
        self._max_entries = import_data[CONF_MAX_ENTRIES]
        return await self.async_step_user({CONF_URL: import_data[CONF_URL]})

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        reconfigure_entry = self._get_reconfigure_entry()
        if not user_input:
            return self.show_user_form(
                user_input={**reconfigure_entry.data},
                description_placeholders={"name": reconfigure_entry.title},
                step_id="reconfigure",
            )

        feed = await async_fetch_feed(self.hass, user_input[CONF_URL])

        if feed.bozo:
            LOGGER.debug("feed bozo_exception: %s", feed.bozo_exception)
            if isinstance(feed.bozo_exception, urllib.error.URLError):
                return self.show_user_form(
                    user_input=user_input,
                    description_placeholders={"name": reconfigure_entry.title},
                    step_id="reconfigure",
                    errors={"base": "url_error"},
                )

        self.hass.config_entries.async_update_entry(reconfigure_entry, data=user_input)
        return self.async_abort(reason="reconfigure_successful")


class FeedReaderOptionsFlowHandler(OptionsFlow):
    """Handle an options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MAX_ENTRIES,
                    default=self.config_entry.options.get(
                        CONF_MAX_ENTRIES, DEFAULT_MAX_ENTRIES
                    ),
                ): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
