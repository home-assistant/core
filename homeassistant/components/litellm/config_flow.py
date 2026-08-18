"""Config flow for LiteLLM integration."""

import logging
from typing import Any, override

from openai import AsyncOpenAI, AuthenticationError, OpenAIError, PermissionDeniedError
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from .const import (
    CONF_PROMPT,
    DOMAIN,
    PLACEHOLDER_API_KEY,
    RECOMMENDED_CONVERSATION_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the proxy."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the API key is invalid."""


def _normalize_url(url: str) -> str:
    """Normalize the proxy URL, ensuring it ends with the OpenAI `/v1` path."""
    parsed = URL(url.strip())
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return str(parsed.with_path(path))


async def _get_models(hass: HomeAssistant, url: str, api_key: str | None) -> list[str]:
    """Fetch the available model names from the LiteLLM proxy.

    Uses the OpenAI-compatible `/v1/models` endpoint, which a LiteLLM proxy
    serves with the configured model names.
    """
    client = AsyncOpenAI(
        base_url=url,
        api_key=api_key or PLACEHOLDER_API_KEY,
        http_client=get_async_client(hass),
    )
    try:
        return [
            model.id async for model in client.with_options(timeout=10.0).models.list()
        ]
    except (AuthenticationError, PermissionDeniedError) as err:
        raise InvalidAuth from err
    except OpenAIError as err:
        raise CannotConnect from err


class LiteLLMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LiteLLM."""

    VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this handler."""
        return {"conversation": ConversationFlowHandler}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            api_key = user_input.get(CONF_API_KEY)
            self._async_abort_entries_match({CONF_URL: url})
            try:
                await _get_models(self.hass, url, api_key)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                data = {CONF_URL: url}
                if api_key:
                    data[CONF_API_KEY] = api_key
                return self.async_create_entry(
                    title=URL(url).host or url,
                    data=data,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL): str,
                    vol.Optional(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


class LiteLLMSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for LiteLLM."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.models: list[str] = []

    async def _fetch_models(self) -> None:
        """Fetch models from the LiteLLM proxy."""
        entry = self._get_entry()
        self.models = await _get_models(
            self.hass, entry.data[CONF_URL], entry.data.get(CONF_API_KEY)
        )


class ConversationFlowHandler(LiteLLMSubentryFlowHandler):
    """Handle conversation subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create a conversation agent."""
        self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a conversation agent."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage conversation agent configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            if self._is_new:
                return self.async_create_entry(
                    title=user_input[CONF_MODEL], data=user_input
                )
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=user_input[CONF_MODEL],
                data=user_input,
            )

        try:
            await self._fetch_models()
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        options = [SelectOptionDict(value=model, label=model) for model in self.models]

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]

        if suggested_llm_apis := self.options.get(CONF_LLM_HASS_API):
            valid_api_ids = {api["value"] for api in hass_apis}
            self.options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_api_ids
            ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL, default=self.options.get(CONF_MODEL)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": self.options.get(
                                CONF_PROMPT,
                                RECOMMENDED_CONVERSATION_OPTIONS[CONF_PROMPT],
                            )
                        },
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        default=self.options.get(
                            CONF_LLM_HASS_API,
                            RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                        ),
                    ): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                }
            ),
        )
