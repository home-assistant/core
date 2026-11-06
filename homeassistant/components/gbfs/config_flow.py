"""Config flow for the GBFS integration."""

import logging
from typing import Any, override

from aiomobilitydatabase.feeds import (
    FeedParseError,
    MobilityFeedsClient,
    SourceConnectionError,
    SystemInfo,
)
import probatio
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN, SUBENTRY_TYPE_STATION

_LOGGER = logging.getLogger(__name__)

URL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        )
    }
)


class InvalidUrl(Exception):
    """The URL isn't an http or https URL."""


class NoStations(Exception):
    """The system publishes no stations."""


async def _async_read_system(hass: HomeAssistant, url: str) -> SystemInfo:
    """Read a system's identity, requiring at least one station."""
    if not _is_http_url(url):
        raise InvalidUrl
    client = MobilityFeedsClient(session=async_get_clientsession(hass))
    feed = await client.get_gbfs_feed_from_url(url)
    system = await feed.get_system_info()
    if not await feed.get_stations():
        raise NoStations
    return system


def _is_http_url(url: str) -> bool:
    try:
        return (parsed := URL(url)).scheme in ("http", "https") and bool(parsed.host)
    except ValueError:
        return False


class GbfsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a GBFS system."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_STATION: StationSubentryFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a system by its auto-discovery URL."""
        return await self._async_step_url("user", user_input, None)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Move the system to a new auto-discovery URL."""
        current_url: str = self._get_reconfigure_entry().data[CONF_URL]
        return await self._async_step_url("reconfigure", user_input, current_url)

    async def _async_step_url(
        self, step_id: str, user_input: dict[str, Any] | None, current_url: str | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url: str = user_input[CONF_URL]
            try:
                system = await _async_read_system(self.hass, url)
            except InvalidUrl:
                errors["base"] = "invalid_url"
            except SourceConnectionError:
                errors["base"] = "cannot_connect"
            except FeedParseError:
                errors["base"] = "invalid_feed"
            except NoStations:
                errors["base"] = "no_stations"
            except Exception:
                _LOGGER.exception("Unexpected exception reading a GBFS system")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(system.system_id)
                if self.source == SOURCE_RECONFIGURE:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates={CONF_URL: url}
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=system.name or system.operator or URL(url).host or url,
                    data={CONF_URL: url},
                )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                URL_SCHEMA, user_input or {CONF_URL: current_url}
            ),
            errors=errors,
        )


class StationSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a station of a GBFS system."""
