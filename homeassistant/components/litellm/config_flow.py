"""Config flow for LiteLLM integration."""

import logging
from typing import Any, TypedDict, cast, override

from openai import AsyncOpenAI, AuthenticationError, OpenAIError, PermissionDeniedError
import probatio
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
    CHAT_COMPLETIONS_ENDPOINT,
    CONF_PROMPT,
    CONF_STT_CUSTOM_PROMPT_KEYWORDS,
    CONF_STT_KEYWORDS,
    CONF_STT_PROMPT,
    DOMAIN,
    MODE_AUDIO_TRANSCRIPTION,
    MODE_CHAT,
    PLACEHOLDER_API_KEY,
    RECOMMENDED_CONVERSATION_OPTIONS,
    STT_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect to the proxy."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class InvalidResponse(HomeAssistantError):
    """Error to indicate the proxy returned an invalid response."""


class Model(TypedDict):
    """LiteLLM model entity used by Home Assistant."""

    model_name: str
    mode: str | None
    supported_endpoints: list[str]


def _normalize_url(url: str) -> str:
    """Normalize the proxy URL, ensuring it ends with the OpenAI `/v1` path."""
    parsed = URL(url.strip())
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1"
    return str(parsed.with_path(path))


async def _get_models(
    hass: HomeAssistant, url: str, api_key: str | None
) -> list[Model]:
    """Fetch the available models from the LiteLLM proxy.

    Uses LiteLLM's model-info endpoint, which serves the configured models and
    their capabilities.
    """
    client = AsyncOpenAI(
        base_url=url,
        api_key=api_key or PLACEHOLDER_API_KEY,
        # Legacy HTTPX clients are supported at runtime only.
        http_client=cast(Any, get_async_client(hass)),
    )
    try:
        response = await client.with_options(timeout=10.0).get(
            "model/info",
            cast_to=object,
            options={"security": {"bearer_auth": True}},
        )
    except (AuthenticationError, PermissionDeniedError) as err:
        raise InvalidAuth from err
    except OpenAIError as err:
        raise CannotConnect from err

    try:
        models = cast(dict[str, list[dict[str, Any]]], response)["data"]
        # LiteLLM may omit capabilities for custom models; flows use their
        # standard chat-completion or STT defaults.
        return [
            {
                "model_name": str(model["model_name"]),
                "mode": model["model_info"].get("mode"),
                "supported_endpoints": model["model_info"].get("supported_endpoints")
                or [],
            }
            for model in models
        ]
    except (AttributeError, KeyError, TypeError) as err:
        raise InvalidResponse from err


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
        return {
            "conversation": ConversationFlowHandler,
            "stt": STTFlowHandler,
        }

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
            except InvalidResponse:
                errors["base"] = "invalid_response"
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
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_URL): str,
                    probatio.Optional(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )


def _get_model_options(
    models: list[Model], mode: str, endpoint: str
) -> list[SelectOptionDict]:
    """Return models matching the mode and endpoint when provided."""
    return [
        SelectOptionDict(value=model["model_name"], label=model["model_name"])
        for model in models
        if model["mode"] in (None, mode)
        and (
            not model["supported_endpoints"] or endpoint in model["supported_endpoints"]
        )
    ]


class LiteLLMSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for LiteLLM."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        self.models: list[Model] = []

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
            if user_input.get(CONF_LLM_HASS_API) is None:
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
        except InvalidResponse:
            return self.async_abort(reason="invalid_response")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        options = _get_model_options(self.models, MODE_CHAT, CHAT_COMPLETIONS_ENDPOINT)

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
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_MODEL, default=self.options.get(CONF_MODEL)
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.DROPDOWN, sort=True
                        ),
                    ),
                    probatio.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": self.options.get(
                                CONF_PROMPT,
                                RECOMMENDED_CONVERSATION_OPTIONS[CONF_PROMPT],
                            )
                        },
                    ): TemplateSelector(),
                    probatio.Optional(
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


class STTFlowHandler(LiteLLMSubentryFlowHandler):
    """Handle STT subentry flow."""

    def __init__(self) -> None:
        """Initialize the subentry flow."""
        super().__init__()
        self.options: dict[str, Any] = {}
        self.last_rendered_custom_prompt_keywords = False

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == SOURCE_USER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """User flow to create an STT entity."""
        self.options = {CONF_STT_CUSTOM_PROMPT_KEYWORDS: False}
        return await self.async_step_init(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of an STT entity."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage STT configuration."""
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        if user_input is not None:
            custom_prompt_keywords = user_input[CONF_STT_CUSTOM_PROMPT_KEYWORDS]
            if custom_prompt_keywords == self.last_rendered_custom_prompt_keywords:
                self.options = user_input.copy()
                for field in (CONF_STT_PROMPT, CONF_STT_KEYWORDS):
                    if not custom_prompt_keywords or not self.options.get(field):
                        self.options.pop(field, None)
                if self._is_new:
                    return self.async_create_entry(
                        title=self.options[CONF_MODEL], data=self.options
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    title=self.options[CONF_MODEL],
                    data=self.options,
                )

            self.options = user_input
            self.last_rendered_custom_prompt_keywords = custom_prompt_keywords
        else:
            self.last_rendered_custom_prompt_keywords = bool(
                self.options.get(CONF_STT_CUSTOM_PROMPT_KEYWORDS, False)
            )

        try:
            await self._fetch_models()
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except InvalidResponse:
            return self.async_abort(reason="invalid_response")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        schema: dict[Any, Any] = {
            probatio.Required(
                CONF_MODEL, default=self.options.get(CONF_MODEL)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=_get_model_options(
                        self.models, MODE_AUDIO_TRANSCRIPTION, STT_ENDPOINT
                    ),
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=True,
                )
            ),
            probatio.Required(
                CONF_STT_CUSTOM_PROMPT_KEYWORDS,
                default=self.options.get(CONF_STT_CUSTOM_PROMPT_KEYWORDS, False),
            ): bool,
        }

        if self.options.get(CONF_STT_CUSTOM_PROMPT_KEYWORDS):
            schema.update(
                {
                    probatio.Optional(
                        CONF_STT_PROMPT,
                        description={
                            "suggested_value": self.options.get(CONF_STT_PROMPT, "")
                        },
                    ): TemplateSelector(),
                    probatio.Optional(
                        CONF_STT_KEYWORDS,
                        description={
                            "suggested_value": self.options.get(CONF_STT_KEYWORDS, "")
                        },
                    ): TemplateSelector(),
                }
            )

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(schema),
        )
