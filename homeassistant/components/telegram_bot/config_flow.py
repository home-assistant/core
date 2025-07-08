"""Config flow for Telegram Bot."""

from collections.abc import Mapping
from ipaddress import AddressValueError, IPv4Network
import logging
from types import MappingProxyType
from typing import Any

from telegram import Bot, ChatFullInfo
from telegram.error import BadRequest, InvalidToken, NetworkError
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import initialize_bot
from .bot import TelegramBotConfigEntry
from .const import (
    ATTR_PARSER,
    BOT_NAME,
    CONF_ALLOWED_CHAT_IDS,
    CONF_BOT_COUNT,
    CONF_CHAT_ID,
    CONF_PROXY_URL,
    CONF_TRUSTED_NETWORKS,
    DEFAULT_TRUSTED_NETWORKS,
    DOMAIN,
    ERROR_FIELD,
    ERROR_MESSAGE,
    ISSUE_DEPRECATED_YAML,
    ISSUE_DEPRECATED_YAML_HAS_MORE_PLATFORMS,
    ISSUE_DEPRECATED_YAML_IMPORT_ISSUE_ERROR,
    PARSER_HTML,
    PARSER_MD,
    PARSER_MD2,
    PARSER_PLAIN_TEXT,
    PLATFORM_BROADCAST,
    PLATFORM_POLLING,
    PLATFORM_WEBHOOKS,
    SECTION_ADVANCED_SETTINGS,
    SUBENTRY_TYPE_ALLOWED_CHAT_IDS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): SelectSelector(
            SelectSelectorConfig(
                options=[
                    PLATFORM_BROADCAST,
                    PLATFORM_POLLING,
                    PLATFORM_WEBHOOKS,
                ],
                translation_key="platforms",
            )
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
        vol.Required(SECTION_ADVANCED_SETTINGS): section(
            vol.Schema(
                {
                    vol.Optional(CONF_PROXY_URL): TextSelector(
                        config=TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                },
            ),
            {"collapsed": True},
        ),
    }
)
STEP_RECONFIGURE_USER_DATA_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): SelectSelector(
            SelectSelectorConfig(
                options=[
                    PLATFORM_BROADCAST,
                    PLATFORM_POLLING,
                    PLATFORM_WEBHOOKS,
                ],
                translation_key="platforms",
            )
        ),
        vol.Required(SECTION_ADVANCED_SETTINGS): section(
            vol.Schema(
                {
                    vol.Optional(CONF_PROXY_URL): TextSelector(
                        config=TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                },
            ),
            {"collapsed": True},
        ),
    }
)
STEP_REAUTH_DATA_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        )
    }
)
STEP_WEBHOOKS_DATA_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Optional(CONF_URL): TextSelector(
            config=TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Required(CONF_TRUSTED_NETWORKS): vol.Coerce(str),
    }
)
OPTIONS_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(
            ATTR_PARSER,
        ): SelectSelector(
            SelectSelectorConfig(
                options=[PARSER_MD, PARSER_MD2, PARSER_HTML, PARSER_PLAIN_TEXT],
                translation_key="parse_mode",
            )
        )
    }
)


class OptionsFlowHandler(OptionsFlow):
    """Options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                self.config_entry.options,
            ),
        )


class TelgramBotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Telegram."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: TelegramBotConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: TelegramBotConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {SUBENTRY_TYPE_ALLOWED_CHAT_IDS: AllowedChatIdsSubEntryFlowHandler}

    def __init__(self) -> None:
        """Create instance of the config flow."""
        super().__init__()
        self._bot: Bot | None = None
        self._bot_name = "Unknown bot"

        # for passing data between steps
        self._step_user_data: dict[str, Any] = {}

    # triggered by async_setup() from __init__.py
    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of config entry from configuration.yaml."""

        telegram_bot: str = f"{import_data[CONF_PLATFORM]} Telegram bot"
        bot_count: int = import_data[CONF_BOT_COUNT]

        import_data[CONF_TRUSTED_NETWORKS] = ",".join(
            import_data[CONF_TRUSTED_NETWORKS]
        )
        import_data[SECTION_ADVANCED_SETTINGS] = {
            CONF_PROXY_URL: import_data.get(CONF_PROXY_URL)
        }
        try:
            config_flow_result: ConfigFlowResult = await self.async_step_user(
                import_data
            )
        except AbortFlow:
            # this happens if the config entry is already imported
            self._create_issue(ISSUE_DEPRECATED_YAML, telegram_bot, bot_count)
            raise
        else:
            errors: dict[str, str] | None = config_flow_result.get("errors")
            if errors:
                error: str = errors.get("base", "unknown")
                self._create_issue(
                    error,
                    telegram_bot,
                    bot_count,
                    config_flow_result["description_placeholders"],
                )
                return self.async_abort(reason="import_failed")

            subentries: list[ConfigSubentryData] = []
            allowed_chat_ids: list[int] = import_data[CONF_ALLOWED_CHAT_IDS]
            assert self._bot is not None, "Bot should be initialized during import"
            for chat_id in allowed_chat_ids:
                chat_name: str = await _async_get_chat_name(self._bot, chat_id)
                subentry: ConfigSubentryData = ConfigSubentryData(
                    data={CONF_CHAT_ID: chat_id},
                    subentry_type=CONF_ALLOWED_CHAT_IDS,
                    title=f"{chat_name} ({chat_id})",
                    unique_id=str(chat_id),
                )
                subentries.append(subentry)
            config_flow_result["subentries"] = subentries

            self._create_issue(
                ISSUE_DEPRECATED_YAML,
                telegram_bot,
                bot_count,
                config_flow_result["description_placeholders"],
            )
            return config_flow_result

    def _create_issue(
        self,
        issue: str,
        telegram_bot_type: str,
        bot_count: int,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> None:
        translation_key: str = (
            ISSUE_DEPRECATED_YAML
            if bot_count == 1
            else ISSUE_DEPRECATED_YAML_HAS_MORE_PLATFORMS
        )
        if issue != ISSUE_DEPRECATED_YAML:
            translation_key = ISSUE_DEPRECATED_YAML_IMPORT_ISSUE_ERROR

        telegram_bot = (
            description_placeholders.get(BOT_NAME, telegram_bot_type)
            if description_placeholders
            else telegram_bot_type
        )
        error_field = (
            description_placeholders.get(ERROR_FIELD, "Unknown error")
            if description_placeholders
            else "Unknown error"
        )
        error_message = (
            description_placeholders.get(ERROR_MESSAGE, "Unknown error")
            if description_placeholders
            else "Unknown error"
        )

        async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_DEPRECATED_YAML,
            breaks_in_ha_version="2025.12.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Telegram Bot",
                "telegram_bot": telegram_bot,
                ERROR_FIELD: error_field,
                ERROR_MESSAGE: error_message,
            },
            learn_more_url="https://github.com/home-assistant/core/pull/144617",
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow to create a new config entry for a Telegram bot."""

        description_placeholders: dict[str, str] = {
            "botfather_username": "@BotFather",
            "botfather_url": "https://t.me/botfather",
        }
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders=description_placeholders,
            )

        # prevent duplicates
        await self.async_set_unique_id(user_input[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        # validate connection to Telegram API
        errors: dict[str, str] = {}
        user_input[CONF_PROXY_URL] = user_input[SECTION_ADVANCED_SETTINGS].get(
            CONF_PROXY_URL
        )
        bot_name = await self._validate_bot(
            user_input, errors, description_placeholders
        )

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        if user_input[CONF_PLATFORM] != PLATFORM_WEBHOOKS:
            await self._shutdown_bot()

            return self.async_create_entry(
                title=bot_name,
                data={
                    CONF_PLATFORM: user_input[CONF_PLATFORM],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_PROXY_URL: user_input[SECTION_ADVANCED_SETTINGS].get(
                        CONF_PROXY_URL
                    ),
                },
                options={
                    # this value may come from yaml import
                    ATTR_PARSER: user_input.get(ATTR_PARSER, PARSER_MD)
                },
                description_placeholders=description_placeholders,
            )

        self._bot_name = bot_name
        self._step_user_data.update(user_input)

        if self.source == SOURCE_IMPORT:
            return await self.async_step_webhooks(
                {
                    CONF_URL: user_input.get(CONF_URL),
                    CONF_TRUSTED_NETWORKS: user_input[CONF_TRUSTED_NETWORKS],
                }
            )
        return await self.async_step_webhooks()

    async def _shutdown_bot(self) -> None:
        """Shutdown the bot if it exists."""
        if self._bot:
            await self._bot.shutdown()

    async def _validate_bot(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
        placeholders: dict[str, str],
    ) -> str:
        try:
            bot = await self.hass.async_add_executor_job(
                initialize_bot, self.hass, MappingProxyType(user_input)
            )
            self._bot = bot

            user = await bot.get_me()
        except InvalidToken as err:
            _LOGGER.warning("Invalid API token")
            errors["base"] = "invalid_api_key"
            placeholders[ERROR_FIELD] = "API key"
            placeholders[ERROR_MESSAGE] = str(err)
            return "Unknown bot"
        except (ValueError, NetworkError) as err:
            _LOGGER.warning("Invalid proxy")
            errors["base"] = "invalid_proxy_url"
            placeholders["proxy_url_error"] = str(err)
            placeholders[ERROR_FIELD] = "proxy url"
            placeholders[ERROR_MESSAGE] = str(err)
            return "Unknown bot"
        else:
            return user.full_name

    async def async_step_webhooks(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config flow for webhook Telegram bot."""

        if not user_input:
            default_trusted_networks = ",".join(
                [str(network) for network in DEFAULT_TRUSTED_NETWORKS]
            )

            if self.source == SOURCE_RECONFIGURE:
                suggested_values = dict(self._get_reconfigure_entry().data)
                if CONF_TRUSTED_NETWORKS not in self._get_reconfigure_entry().data:
                    suggested_values[CONF_TRUSTED_NETWORKS] = default_trusted_networks

                return self.async_show_form(
                    step_id="webhooks",
                    data_schema=self.add_suggested_values_to_schema(
                        STEP_WEBHOOKS_DATA_SCHEMA,
                        suggested_values,
                    ),
                )

            return self.async_show_form(
                step_id="webhooks",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_WEBHOOKS_DATA_SCHEMA,
                    {
                        CONF_TRUSTED_NETWORKS: default_trusted_networks,
                    },
                ),
            )

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {BOT_NAME: self._bot_name}
        self._validate_webhooks(user_input, errors, description_placeholders)
        if errors:
            return self.async_show_form(
                step_id="webhooks",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_WEBHOOKS_DATA_SCHEMA,
                    user_input,
                ),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        await self._shutdown_bot()

        if self.source == SOURCE_RECONFIGURE:
            user_input.update(self._step_user_data)
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title=self._bot_name,
                data_updates=user_input,
            )

        return self.async_create_entry(
            title=self._bot_name,
            data={
                CONF_PLATFORM: self._step_user_data[CONF_PLATFORM],
                CONF_API_KEY: self._step_user_data[CONF_API_KEY],
                CONF_PROXY_URL: self._step_user_data[SECTION_ADVANCED_SETTINGS].get(
                    CONF_PROXY_URL
                ),
                CONF_URL: user_input.get(CONF_URL),
                CONF_TRUSTED_NETWORKS: user_input[CONF_TRUSTED_NETWORKS],
            },
            options={ATTR_PARSER: self._step_user_data.get(ATTR_PARSER, PARSER_MD)},
            description_placeholders=description_placeholders,
        )

    def _validate_webhooks(
        self,
        user_input: dict[str, Any],
        errors: dict[str, str],
        description_placeholders: dict[str, str],
    ) -> None:
        # validate URL
        url: str | None = user_input.get(CONF_URL)
        if url is None:
            try:
                get_url(self.hass, require_ssl=True, allow_internal=False)
            except NoURLAvailableError:
                errors["base"] = "no_url_available"
                description_placeholders[ERROR_FIELD] = "URL"
                description_placeholders[ERROR_MESSAGE] = (
                    "URL is required since you have not configured an external URL in Home Assistant"
                )
                return
        elif not url.startswith("https"):
            errors["base"] = "invalid_url"
            description_placeholders[ERROR_FIELD] = "URL"
            description_placeholders[ERROR_MESSAGE] = "URL must start with https"
            return

        # validate trusted networks
        csv_trusted_networks: list[str] = []
        formatted_trusted_networks: str = (
            user_input[CONF_TRUSTED_NETWORKS].lstrip("[").rstrip("]")
        )
        for trusted_network in cv.ensure_list_csv(formatted_trusted_networks):
            formatted_trusted_network: str = trusted_network.strip("'")
            try:
                IPv4Network(formatted_trusted_network)
            except (AddressValueError, ValueError) as err:
                errors["base"] = "invalid_trusted_networks"
                description_placeholders[ERROR_FIELD] = "trusted networks"
                description_placeholders[ERROR_MESSAGE] = str(err)
                return
            else:
                csv_trusted_networks.append(formatted_trusted_network)
        user_input[CONF_TRUSTED_NETWORKS] = csv_trusted_networks

        return

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure Telegram bot."""

        api_key: str = self._get_reconfigure_entry().data[CONF_API_KEY]
        await self.async_set_unique_id(api_key)
        self._abort_if_unique_id_mismatch()

        if not user_input:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_RECONFIGURE_USER_DATA_SCHEMA,
                    {
                        **self._get_reconfigure_entry().data,
                        SECTION_ADVANCED_SETTINGS: {
                            CONF_PROXY_URL: self._get_reconfigure_entry().data.get(
                                CONF_PROXY_URL
                            ),
                        },
                    },
                ),
            )
        user_input[CONF_PROXY_URL] = user_input[SECTION_ADVANCED_SETTINGS].get(
            CONF_PROXY_URL
        )

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        user_input[CONF_API_KEY] = api_key
        bot_name = await self._validate_bot(
            user_input, errors, description_placeholders
        )
        self._bot_name = bot_name

        if errors:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_RECONFIGURE_USER_DATA_SCHEMA,
                    {
                        **user_input,
                        SECTION_ADVANCED_SETTINGS: {
                            CONF_PROXY_URL: user_input.get(CONF_PROXY_URL),
                        },
                    },
                ),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        if user_input[CONF_PLATFORM] != PLATFORM_WEBHOOKS:
            await self._shutdown_bot()

            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), title=bot_name, data_updates=user_input
            )

        self._step_user_data.update(user_input)
        return await self.async_step_webhooks()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth confirm step."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_REAUTH_DATA_SCHEMA, self._get_reauth_entry().data
                ),
            )

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        bot_name = await self._validate_bot(
            user_input, errors, description_placeholders
        )
        await self._shutdown_bot()

        if errors:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_REAUTH_DATA_SCHEMA, self._get_reauth_entry().data
                ),
                errors=errors,
                description_placeholders=description_placeholders,
            )

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), title=bot_name, data_updates=user_input
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
            bot = config_entry.runtime_data.bot

            chat_id: int = user_input[CONF_CHAT_ID]
            chat_name = await _async_get_chat_name(bot, chat_id)
            if chat_name:
                return self.async_create_entry(
                    title=f"{chat_name} ({chat_id})",
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
        return chat_info.effective_name or str(chat_id)
    except BadRequest:
        return ""
