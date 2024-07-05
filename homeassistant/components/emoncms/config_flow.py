"""Configflow for the emoncms integration."""

from datetime import timedelta
from typing import Any

from pyemoncms import EmoncmsClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EXCLUDE_FEEDID,
    CONF_FEED_LIST,
    CONF_ONLY_INCLUDE_FEEDID,
    CONF_SENSOR_NAMES,
    DOMAIN,
    LOGGER,
)

CONF_MESSAGE = "message"
CONF_SUCCESS = "success"
FEED_ID = "id"
FEED_NAME = "name"
FEED_TAG = "tag"


def get_options(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the selector options with the feed list."""
    return [
        {
            "value": feed[FEED_ID],
            "label": f"{feed[FEED_ID]}|{feed[FEED_TAG]}|{feed[FEED_NAME]}",
        }
        for feed in feeds
    ]


async def get_feed_list(hass: HomeAssistant, url: str, api_key: str) -> dict[str, Any]:
    """Check connection to emoncms and return feed list if successful."""
    emoncms_client = EmoncmsClient(
        url,
        api_key,
        session=async_get_clientsession(hass),
    )
    return await emoncms_client.async_request("/feed/list.json")


class EmoncmsConfigFlow(ConfigFlow, domain=DOMAIN):
    """emoncms integration UI config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowWithConfigEntry:
        """Get the options flow for this handler."""
        return EmoncmsOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initiate a flow via the UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_ID: user_input[CONF_ID],
                    CONF_URL: user_input[CONF_URL],
                }
            )
            result = await get_feed_list(
                self.hass, user_input[CONF_URL], user_input[CONF_API_KEY]
            )
            if not result[CONF_SUCCESS]:
                errors["base"] = result[CONF_MESSAGE]
            else:
                return self.async_create_entry(
                    title=user_input[CONF_ID], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ID): str,
                        vol.Required(CONF_URL): str,
                        vol.Required(CONF_API_KEY): str,
                        vol.Required(CONF_SCAN_INTERVAL, default=30): int,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: ConfigType) -> ConfigFlowResult:
        """Import config from yaml."""
        value_template = None
        if CONF_VALUE_TEMPLATE in import_info:
            value_template = import_info[CONF_VALUE_TEMPLATE].template
        config = {
            CONF_ID: import_info[CONF_ID],
            CONF_API_KEY: import_info[CONF_API_KEY],
            CONF_EXCLUDE_FEEDID: import_info.get(CONF_EXCLUDE_FEEDID),
            CONF_ONLY_INCLUDE_FEEDID: import_info.get(CONF_ONLY_INCLUDE_FEEDID),
            CONF_SENSOR_NAMES: import_info.get(CONF_SENSOR_NAMES),
            CONF_SCAN_INTERVAL: timedelta.total_seconds(
                import_info.get(CONF_SCAN_INTERVAL, timedelta(seconds=30))
            ),
            CONF_UNIT_OF_MEASUREMENT: import_info.get(CONF_UNIT_OF_MEASUREMENT),
            CONF_URL: import_info[CONF_URL],
            CONF_VALUE_TEMPLATE: value_template,
        }
        LOGGER.debug(config)
        result = await self.async_step_user(config)
        if errors := result.get("errors"):
            return self.async_abort(reason=errors["base"])
        return result


class EmoncmsOptionsFlow(OptionsFlowWithConfigEntry):
    """Emoncms Options flow handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        default_url = self._config_entry.data[CONF_URL]
        default_scan_interval = self._config_entry.data[CONF_SCAN_INTERVAL]
        default_api_key = self._config_entry.data[CONF_API_KEY]
        exclude_feeds = self._config_entry.data.get(CONF_EXCLUDE_FEEDID)
        include_only_feeds = self._config_entry.data.get(CONF_ONLY_INCLUDE_FEEDID)
        selected_feeds = []
        if include_only_feeds:
            selected_feeds = [str(feed) for feed in include_only_feeds]
        options: Any = selected_feeds
        result = await get_feed_list(self.hass, default_url, default_api_key)
        if not result[CONF_SUCCESS]:
            errors["base"] = result[CONF_MESSAGE]
        else:
            if include_only_feeds:
                selected_feeds = [
                    feed[FEED_ID]
                    for feed in result[CONF_MESSAGE]
                    if int(feed[FEED_ID]) in include_only_feeds
                ]
            if exclude_feeds:
                selected_feeds = [
                    feed[FEED_ID]
                    for feed in result[CONF_MESSAGE]
                    if int(feed[FEED_ID]) not in exclude_feeds
                ]
            options = get_options(result[CONF_MESSAGE])
        if CONF_FEED_LIST in self._config_entry.data:
            selected_feeds = self._config_entry.data[CONF_FEED_LIST]
        dropdown = {"options": options, "mode": "dropdown", "multiple": True}
        if user_input:
            default_url = user_input[CONF_URL]
            default_api_key = user_input[CONF_API_KEY]
            default_scan_interval = user_input[CONF_SCAN_INTERVAL]
            selected_feeds = user_input[CONF_FEED_LIST]
            user_input[CONF_ID] = self._config_entry.data[CONF_ID]
            user_input[CONF_EXCLUDE_FEEDID] = None
            user_input[CONF_ONLY_INCLUDE_FEEDID] = None
            user_input[CONF_VALUE_TEMPLATE] = self._config_entry.data[
                CONF_VALUE_TEMPLATE
            ]
            if self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            ):
                LOGGER.debug("entry updated")
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=default_url): str,
                    vol.Required(CONF_API_KEY, default=default_api_key): str,
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=default_scan_interval
                    ): int,
                    vol.Required(CONF_FEED_LIST, default=selected_feeds): selector(
                        {"select": dropdown}
                    ),
                }
            ),
            errors=errors,
        )
