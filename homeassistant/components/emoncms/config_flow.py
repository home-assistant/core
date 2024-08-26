"""Configflow for the emoncms integration."""

from typing import Any

from pyemoncms import EmoncmsClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_MESSAGE,
    CONF_ONLY_INCLUDE_FEEDID,
    CONF_SUCCESS,
    DOMAIN,
    FEED_ID,
    FEED_NAME,
    FEED_TAG,
    LOGGER,
)


def get_options(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the selector options with the feed list."""
    return [
        {
            "value": feed[FEED_ID],
            "label": f"{feed[FEED_ID]}|{feed[FEED_TAG]}|{feed[FEED_NAME]}",
        }
        for feed in feeds
    ]


def sensor_name(url: str) -> str:
    """Return sensor name."""
    sensorip = url.rsplit("//", maxsplit=1)[-1]
    return f"emoncms@{sensorip}"


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

    url: str
    api_key: str
    include_only_feeds: list | None = None
    dropdown: dict = {}

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
                    CONF_URL: user_input[CONF_URL],
                }
            )
            result = await get_feed_list(
                self.hass, user_input[CONF_URL], user_input[CONF_API_KEY]
            )
            if not result[CONF_SUCCESS]:
                errors["base"] = result[CONF_MESSAGE]
            else:
                self.include_only_feeds = user_input.get(CONF_ONLY_INCLUDE_FEEDID)
                self.url = user_input[CONF_URL]
                self.api_key = user_input[CONF_API_KEY]
                options = get_options(result[CONF_MESSAGE])
                self.dropdown = {
                    "options": options,
                    "mode": "dropdown",
                    "multiple": True,
                }
                return await self.async_step_choose_feeds()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_URL): str,
                        vol.Required(CONF_API_KEY): str,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_choose_feeds(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose feeds to import."""
        errors: dict[str, str] = {}
        include_only_feeds: list = []
        if user_input or self.include_only_feeds is not None:
            if self.include_only_feeds is not None:
                include_only_feeds = self.include_only_feeds
            elif user_input:
                include_only_feeds = user_input[CONF_ONLY_INCLUDE_FEEDID]
            return self.async_create_entry(
                title=sensor_name(self.url),
                data={
                    CONF_URL: self.url,
                    CONF_API_KEY: self.api_key,
                    CONF_ONLY_INCLUDE_FEEDID: include_only_feeds,
                },
            )
        return self.async_show_form(
            step_id="choose_feeds",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ONLY_INCLUDE_FEEDID,
                        default=include_only_feeds,
                    ): selector({"select": self.dropdown}),
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_info: ConfigType) -> ConfigFlowResult:
        """Import config from yaml."""
        url = import_info[CONF_URL]
        api_key = import_info[CONF_API_KEY]
        include_only_feeds = None
        if import_info.get(CONF_ONLY_INCLUDE_FEEDID) is not None:
            include_only_feeds = list(map(str, import_info[CONF_ONLY_INCLUDE_FEEDID]))
        config = {
            CONF_API_KEY: api_key,
            CONF_ONLY_INCLUDE_FEEDID: include_only_feeds,
            CONF_URL: url,
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
        data = self.options if self.options else self._config_entry.data
        url = data[CONF_URL]
        api_key = data[CONF_API_KEY]
        include_only_feeds = data.get(CONF_ONLY_INCLUDE_FEEDID, [])
        options: list = include_only_feeds
        result = await get_feed_list(self.hass, url, api_key)
        if not result[CONF_SUCCESS]:
            errors["base"] = result[CONF_MESSAGE]
        else:
            options = get_options(result[CONF_MESSAGE])
        dropdown = {"options": options, "mode": "dropdown", "multiple": True}
        if user_input:
            include_only_feeds = user_input[CONF_ONLY_INCLUDE_FEEDID]
            return self.async_create_entry(
                title=sensor_name(url),
                data={
                    CONF_URL: url,
                    CONF_API_KEY: api_key,
                    CONF_ONLY_INCLUDE_FEEDID: include_only_feeds,
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ONLY_INCLUDE_FEEDID, default=include_only_feeds
                    ): selector({"select": dropdown}),
                }
            ),
            errors=errors,
        )
