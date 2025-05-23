"""Config flow for Telegram Bot."""

from types import MappingProxyType
from typing import Any

from telegram import Bot, ChatFullInfo, User
from telegram.error import BadRequest, InvalidToken
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import (
    ATTR_PARSER,
    CONF_ALLOWED_CHAT_IDS,
    CONF_CHAT_ID,
    CONF_PLATFORM,
    CONF_PROXY_URL,
    CONF_TRUSTED_NETWORKS,
    CONF_URL,
    DOMAIN,
    PARSER_HTML,
    PARSER_MD,
    PARSER_MD2,
    TelegramBotConfigEntry,
    initialize_bot,
)


class TelgramBotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Telegram."""

    VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: TelegramBotConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {CONF_ALLOWED_CHAT_IDS: AllowedChatIdsSubEntryFlowHandler}

    # triggered by async_setup() from __init__.py
    async def async_step_import(self, import_data: dict[str, str]) -> ConfigFlowResult:
        """Handle import of config entry from configuration.yaml."""
        return await self.async_step_user(import_data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow to create a new config entry for a Telegram bot."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # prevent duplicates
            await self.async_set_unique_id(user_input.get(CONF_API_KEY))
            self._abort_if_unique_id_configured()

            # use bot name as title for the config entry
            # this also validates the config entry
            bot: Bot = await self.hass.async_add_executor_job(
                initialize_bot, self.hass, MappingProxyType(user_input)
            )
            try:
                user: User = await bot.get_me()
            except InvalidToken:
                errors["base"] = "invalid_api_key"

            bot_name: str = user.full_name

            if not errors:
                subentries: list[ConfigSubentryData] = []
                allowed_chat_ids: list[int] = user_input.get(CONF_ALLOWED_CHAT_IDS, [])
                for chat_id in allowed_chat_ids:
                    chat_name: str = await _async_get_chat_name(bot, chat_id)
                    subentry: ConfigSubentryData = ConfigSubentryData(
                        data={CONF_CHAT_ID: chat_id},
                        subentry_type=CONF_ALLOWED_CHAT_IDS,
                        title=chat_name,
                        unique_id=str(chat_id),
                    )
                    subentries.append(subentry)

                return self.async_create_entry(
                    title=bot_name,
                    data={
                        CONF_PLATFORM: user_input.get(CONF_PLATFORM),
                        CONF_API_KEY: user_input.get(CONF_API_KEY),
                        ATTR_PARSER: user_input.get(ATTR_PARSER),
                        CONF_PROXY_URL: user_input.get(CONF_PROXY_URL),
                    },
                    options={
                        CONF_URL: user_input.get(CONF_URL),
                        CONF_TRUSTED_NETWORKS: user_input.get(CONF_TRUSTED_NETWORKS),
                    },
                    subentries=subentries,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PLATFORM): SelectSelector(
                        SelectSelectorConfig(
                            options=["broadcast", "polling", "webhooks"],
                            translation_key="platforms",
                        )
                    ),
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(ATTR_PARSER, default=PARSER_MD): SelectSelector(
                        SelectSelectorConfig(
                            options=[PARSER_MD, PARSER_MD2, PARSER_HTML],
                            translation_key="parsers",
                        )
                    ),
                    vol.Optional(CONF_PROXY_URL): str,
                }
            ),
            errors=errors,
        )


class AllowedChatIdsSubEntryFlowHandler(ConfigSubentryFlow):
    """Handle a subentry flow for creating chat ID."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Create allowed chat ID."""

        errors: dict[str, str] = {}

        if user_input is not None:
            config_entry: TelegramBotConfigEntry = self._get_entry()
            bot: Bot = config_entry.runtime_data

            chat_id: int = user_input[CONF_CHAT_ID]
            for existing_subentry in config_entry.subentries.values():
                if existing_subentry.unique_id == str(chat_id):
                    return self.async_abort(reason="already_configured")

            chat_name: str = await _async_get_chat_name(bot, chat_id)
            if chat_name:
                return self.async_create_entry(
                    title=chat_name,
                    data={CONF_CHAT_ID: chat_id},
                    unique_id=str(chat_id),
                )

            errors["base"] = "chat_not_found"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_CHAT_ID): vol.Coerce(int)}),
            errors=errors,
        )


async def _async_get_chat_name(bot: Bot, chat_id: int) -> str:
    try:
        chat_info: ChatFullInfo = await bot.get_chat(chat_id)
        title: str = chat_info.effective_name or str(chat_id)
    except BadRequest:
        return ""
    else:
        return title
