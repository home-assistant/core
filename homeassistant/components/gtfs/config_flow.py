"""Config flow for the GTFS integration."""

import asyncio
from functools import partial
import json
import logging
import threading
from typing import Any, override
from uuid import uuid4

import probatio
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
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
    CONF_DATABASE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    DOMAIN,
    FLOW_DATABASES,
    SUBENTRY_TYPE_ROUTE,
)
from .feed import (
    CannotConnect,
    GtfsConfigEntry,
    InvalidFeed,
    async_fetch_feed,
    feed_database_path,
    list_stops,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        )
    }
)


class GtfsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GTFS."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._url: str | None = None
        self._database: str | None = None
        self._title: str | None = None
        self._load_task: asyncio.Task[str | None] | None = None
        self._cancelled = threading.Event()
        self._load_error: str | None = None
        self._database_kept = False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a feed URL."""
        return await self._async_step_url("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Download the feed again, optionally from a new URL."""
        if self._url is None:
            self._url = self._get_reconfigure_entry().data[CONF_URL]
        return await self._async_step_url("reconfigure", user_input)

    async def _async_step_url(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Ask for a feed URL, then load it into a new database."""
        errors: dict[str, str] = {}
        if self._load_error:
            errors["base"] = self._load_error
            self._load_error = None
        if user_input is not None:
            url: str = user_input[CONF_URL].strip()
            self._url = url
            if not _is_http_url(url):
                errors[CONF_URL] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_URL: url})
                self._set_database(f"{uuid4().hex}.sqlite")
                return await self.async_step_load_feed()
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_URL: self._url}
            ),
            errors=errors,
        )

    def _set_database(self, database: str) -> None:
        """Track the database so the startup sweep leaves its files alone."""
        flow_databases = self.hass.data.setdefault(FLOW_DATABASES, set())
        if self._database is not None:
            flow_databases.discard(self._database)
        flow_databases.add(database)
        self._database = database

    async def async_step_load_feed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Download and import the feed, reporting progress."""
        assert self._url is not None
        assert self._database is not None
        # An eager task may already be done; finishing here would make
        # async_configure re-run the user step.
        if self._load_task is None:
            self._cancelled = threading.Event()
            self._load_task = self.hass.async_create_task(
                async_fetch_feed(
                    self.hass,
                    self._url,
                    feed_database_path(self.hass, self._database),
                    self._cancelled,
                )
            )
        elif self._load_task.done():
            task, self._load_task = self._load_task, None
            try:
                self._title = task.result()
            except CannotConnect as err:
                _LOGGER.debug("Could not download GTFS feed: %s", err)
                self._load_error = "cannot_connect"
            except InvalidFeed as err:
                _LOGGER.warning("Could not load GTFS feed: %s", err)
                self._load_error = "invalid_feed"
            except Exception:
                _LOGGER.exception("Unexpected exception loading GTFS feed")
                self._load_error = "unknown"
            else:
                return self.async_show_progress_done(next_step_id="finish")
            return self.async_show_progress_done(
                next_step_id="reconfigure"
                if self.source == SOURCE_RECONFIGURE
                else "user"
            )
        return self.async_show_progress(
            step_id="load_feed",
            progress_action="load_feed",
            progress_task=self._load_task,
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create or update the entry after a successful import."""
        assert self._url is not None
        assert self._database is not None
        self._async_abort_entries_match({CONF_URL: self._url})
        self._database_kept = True
        if self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            old_path = feed_database_path(self.hass, entry.data[CONF_DATABASE])
            result = self.async_update_reload_and_abort(
                entry, data_updates={CONF_URL: self._url, CONF_DATABASE: self._database}
            )
            # Until it reloads, the entry reads from its open handle on the old file.
            await self.hass.async_add_executor_job(
                partial(old_path.unlink, missing_ok=True)
            )
            return result
        return self.async_create_entry(
            title=self._title or URL(self._url).host or self._url,
            data={CONF_URL: self._url, CONF_DATABASE: self._database},
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {SUBENTRY_TYPE_ROUTE: RouteSubentryFlowHandler}

    @override
    @callback
    def async_remove(self) -> None:
        """Delete the imported feed if the flow ends without using it."""
        if self._database is None:
            return
        self.hass.data[FLOW_DATABASES].discard(self._database)
        if not self._database_kept:
            self._cancelled.set()
            self.hass.async_add_executor_job(
                partial(
                    feed_database_path(self.hass, self._database).unlink,
                    missing_ok=True,
                )
            )


class RouteSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a route between two stops."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Pick the origin and destination stops."""
        entry: GtfsConfigEntry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")
        stops = await self.hass.async_add_executor_job(list_stops, entry.runtime_data)
        errors: dict[str, str] = {}
        if user_input is not None:
            origin: str = user_input[CONF_ORIGIN]
            destination: str = user_input[CONF_DESTINATION]
            if origin == destination:
                errors["base"] = "same_stop"
            else:
                return self.async_create_entry(
                    title=f"{stops[origin]} to {stops[destination]}",
                    data={CONF_ORIGIN: origin, CONF_DESTINATION: destination},
                    unique_id=json.dumps([origin, destination]),
                )
        stop_selector = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=stop_id, label=f"{name} ({stop_id})")
                    for stop_id, name in stops.items()
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        schema = probatio.Schema(
            {
                probatio.Required(CONF_ORIGIN): stop_selector,
                probatio.Required(CONF_DESTINATION): stop_selector,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )


def _is_http_url(url: str) -> bool:
    try:
        return (parsed := URL(url)).scheme in ("http", "https") and bool(parsed.host)
    except ValueError:
        return False
