"""Config flow for OpenAI Conversation integration."""

from collections.abc import Mapping
import json
import logging
from typing import Any, override

import openai
import probatio

from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_CLIENT_ID,
    CONF_LLM_HASS_API,
    CONF_NAME,
    CONF_PROMPT,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.typing import VolDictType

from .chatgpt_auth import (
    CLIENT_ID_PREFIX,
    PLAN_SCOPE,
    RESOURCE,
    AuthorizationRequest,
    ChatGPTAuth,
    ChatGPTCredentials,
    ChatGPTSubscriptionClient,
    async_get_agent_host_id,
    async_get_subscription_models,
    async_get_subscription_models_for_credentials,
    async_token_request,
    async_validate_id_token,
    create_authorization_request,
    credentials_from_token,
    is_chatgpt_entry,
    parse_callback_url,
    subscription_model_options,
)
from .const import (
    AUTH_METHOD_API_KEY,
    AUTH_METHOD_CHATGPT,
    CONF_AUTH_METHOD,
    CONF_CALLBACK_URL,
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_ID_TOKEN,
    CONF_IMAGE_MODEL,
    CONF_MAX_TOKENS,
    CONF_PRO_MODE,
    CONF_REASONING_EFFORT,
    CONF_REASONING_SUMMARY,
    CONF_RECOMMENDED,
    CONF_SERVICE_TIER,
    CONF_STORE_RESPONSES,
    CONF_SUB,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_TTS_SPEED,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_CONTEXT_SIZE,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_INLINE_CITATIONS,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
    CONF_WEB_SEARCH_USER_LOCATION,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_STT_NAME,
    DEFAULT_STT_PROMPT,
    DEFAULT_TTS_NAME,
    DOMAIN,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_CODE_INTERPRETER,
    RECOMMENDED_CONVERSATION_OPTIONS,
    RECOMMENDED_IMAGE_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_PRO_MODE,
    RECOMMENDED_REASONING_EFFORT,
    RECOMMENDED_REASONING_SUMMARY,
    RECOMMENDED_SERVICE_TIER,
    RECOMMENDED_STORE_RESPONSES,
    RECOMMENDED_STT_MODEL,
    RECOMMENDED_STT_OPTIONS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_TTS_OPTIONS,
    RECOMMENDED_TTS_SPEED,
    RECOMMENDED_VERBOSITY,
    RECOMMENDED_WEB_SEARCH,
    RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
    RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
    RECOMMENDED_WEB_SEARCH_USER_LOCATION,
    UNSUPPORTED_CODE_INTERPRETER_MODELS,
    UNSUPPORTED_FLEX_SERVICE_TIERS_MODELS,
    UNSUPPORTED_IMAGE_MODELS,
    UNSUPPORTED_MODELS,
    UNSUPPORTED_PRIORITY_SERVICE_TIERS_MODELS,
    UNSUPPORTED_WEB_SEARCH_MODELS,
)

_LOGGER = logging.getLogger(__name__)

# Title of a config entry which authenticates with a ChatGPT plan.
DEFAULT_CHATGPT_TITLE = "ChatGPT subscription"

STEP_API_KEY_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
    }
)
STEP_AUTH_METHOD_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_AUTH_METHOD, default=AUTH_METHOD_API_KEY
        ): SelectSelector(
            SelectSelectorConfig(
                options=[AUTH_METHOD_API_KEY, AUTH_METHOD_CHATGPT],
                translation_key=CONF_AUTH_METHOD,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)
STEP_CALLBACK_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CALLBACK_URL): str,
    }
)

# Subentry types the ChatGPT plan usage route cannot provide.
SPEECH_SUBENTRY_TYPES = ("stt", "tts")


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_API_KEY_DATA_SCHEMA with values provided by the
    user.
    """
    client = openai.AsyncOpenAI(
        api_key=data[CONF_API_KEY],
        http_client=get_async_client(hass),
    )
    await client.models.list(timeout=10.0)


class OpenAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenAI Conversation."""

    VERSION = 2
    MINOR_VERSION = 7

    # Pending Sign in with ChatGPT authorization attempt.
    _siwc_request: AuthorizationRequest

    # Credentials and entry data of a completed sign in, held while the user
    # picks a model before a new entry is created.
    _siwc_credentials: ChatGPTCredentials
    _siwc_data: dict[str, Any]
    _siwc_models: list[str]

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step.

        The authentication method and the credential are asked in separate
        steps: a Home Assistant form step cannot hide a field conditionally, so
        the API key field must not sit in the form that also shows the method.
        """
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_AUTH_METHOD_DATA_SCHEMA,
                errors={},
            )
        if user_input.get(CONF_AUTH_METHOD) == AUTH_METHOD_CHATGPT:
            return await self.async_step_chatgpt()
        return await self.async_step_api_key()

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the API key of a new entry."""
        return await self._async_step_api_key(user_input, "api_key")

    @callback
    def _siwc_entry(self) -> ConfigEntry | None:
        """Return the entry which is being reauthenticated or reconfigured."""
        if self.source == SOURCE_REAUTH:
            return self._get_reauth_entry()
        if self.source == SOURCE_RECONFIGURE:
            return self._get_reconfigure_entry()
        return None

    async def _async_catalog_models(self, credentials: ChatGPTCredentials) -> list[str]:
        """Return the first model of the signed in account's catalog, if any.

        The catalog is only used to preselect a model. Reading it can fail
        (OpenAI returned a transient 520 while this was written), and that must
        not fail the sign in: the default model is used instead.
        """
        try:
            return await async_get_subscription_models_for_credentials(
                self.hass, credentials
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Could not read the OpenAI model catalog, using the default "
                "model instead: %s",
                err,
            )
            return []

    async def _async_catalog_default(
        self, credentials: ChatGPTCredentials
    ) -> str | None:
        """Return the first model of the signed in account's catalog, if any."""
        models = await self._async_catalog_models(credentials)
        return models[0] if models else None

    @callback
    def _async_remove_speech_subentries(self, entry: ConfigEntry) -> None:
        """Remove the speech-to-text and text-to-speech subentries of an entry.

        The plan usage route does not provide those APIs. A subentry which is
        not present is simply not removed, so this is idempotent.
        """
        for subentry in list(entry.subentries.values()):
            if subentry.subentry_type in SPEECH_SUBENTRY_TYPES:
                self.hass.config_entries.async_remove_subentry(
                    entry, subentry.subentry_id
                )

    @callback
    def _async_bind_catalog_model(self, entry: ConfigEntry, model: str) -> None:
        """Store a catalog model on the subentries which do not have one.

        The plan usage route rejects the regular API default model, so an entry
        which switched to the plan must not keep falling back to it.
        """
        for subentry in entry.subentries.values():
            if (
                subentry.subentry_type in ("conversation", "ai_task_data")
                and subentry.data.get(CONF_CHAT_MODEL) is None
            ):
                self.hass.config_entries.async_update_subentry(
                    entry,
                    subentry,
                    data={**subentry.data, CONF_CHAT_MODEL: model},
                )

    async def _async_step_api_key(
        self, user_input: dict[str, Any] | None, step_id: str
    ) -> ConfigFlowResult:
        """Handle an API key form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (api_key := user_input.get(CONF_API_KEY)):
                errors[CONF_API_KEY] = "api_key_required"
            else:
                # The auth method is a flow-only choice: API key entries keep
                # their historical data layout without it.
                data = {CONF_API_KEY: api_key}
                self._async_abort_entries_match(data)
                try:
                    await validate_input(self.hass, data)
                except openai.APIConnectionError:
                    errors["base"] = "cannot_connect"
                except openai.AuthenticationError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"
                else:
                    if self.source in (SOURCE_REAUTH, SOURCE_RECONFIGURE):
                        entry = (
                            self._get_reauth_entry()
                            if self.source == SOURCE_REAUTH
                            else self._get_reconfigure_entry()
                        )
                        if is_chatgpt_entry(entry):
                            # Switching a plan entry back to an API key replaces
                            # the whole data layout and drops the account scoped
                            # unique id.
                            if entry.update_listeners:
                                return self.async_update_and_abort(
                                    entry, data=data, unique_id=None
                                )
                            return self.async_update_reload_and_abort(
                                entry, data=data, unique_id=None
                            )
                        if entry.update_listeners:
                            return self.async_update_and_abort(entry, data_updates=data)
                        return self.async_update_reload_and_abort(
                            entry, data_updates=data
                        )
                    return self.async_create_entry(
                        title="ChatGPT",
                        data=data,
                        subentries=[
                            {
                                "subentry_type": "conversation",
                                "data": RECOMMENDED_CONVERSATION_OPTIONS,
                                "title": DEFAULT_CONVERSATION_NAME,
                                "unique_id": None,
                            },
                            {
                                "subentry_type": "ai_task_data",
                                "data": RECOMMENDED_AI_TASK_OPTIONS,
                                "title": DEFAULT_AI_TASK_NAME,
                                "unique_id": None,
                            },
                            {
                                "subentry_type": "stt",
                                "data": RECOMMENDED_STT_OPTIONS,
                                "title": DEFAULT_STT_NAME,
                                "unique_id": None,
                            },
                            {
                                "subentry_type": "tts",
                                "data": RECOMMENDED_TTS_OPTIONS,
                                "title": DEFAULT_TTS_NAME,
                                "unique_id": None,
                            },
                        ],
                    )

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                STEP_API_KEY_DATA_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={
                "instructions_url": "https://www.home-assistant.io/integrations/openai_conversation/#prerequisites",
            },
        )

    def _show_chatgpt_form(
        self, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the Sign in with ChatGPT form."""
        return self.async_show_form(
            step_id="chatgpt",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CALLBACK_DATA_SCHEMA, None
            ),
            errors=errors or {},
            description_placeholders={"auth_url": self._siwc_request.url},
        )

    async def async_step_chatgpt(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start a Sign in with ChatGPT authorization.

        Home Assistant cannot receive the loopback callback (the browser is
        normally on another machine), so the authorization URL is shown to the
        user and they paste back the URL their browser ended up on.
        """
        entry = self._siwc_entry()

        if user_input is not None:
            try:
                return await self._async_step_chatgpt_callback(user_input, entry)
            except AbortFlow:
                # The flow aborts on purpose (an entry already exists, ...).
                raise
            except Exception:
                # A user must never be left with a bare "unknown error": log
                # what happened and ask them to start the sign in again.
                _LOGGER.exception("Unexpected error during the ChatGPT sign in")
                return self._show_chatgpt_form({"base": "unexpected_error"})

        self._siwc_request = create_authorization_request(
            # A saved client id re-authorizes a known registration; a retained
            # ID token identifies the account and skips the account selector.
            client_id=entry.data.get(CONF_CLIENT_ID) if entry else None,
            ext_agent_host_id=await async_get_agent_host_id(self.hass),
            id_token_hint=entry.data.get(CONF_ID_TOKEN) if entry else None,
        )
        return self._show_chatgpt_form()

    async def _async_step_chatgpt_callback(
        self, user_input: dict[str, Any], entry: ConfigEntry | None
    ) -> ConfigFlowResult:
        """Validate the returned callback and complete the sign in."""
        request = self._siwc_request
        params = parse_callback_url(user_input[CONF_CALLBACK_URL])

        if error := params.get("error"):
            _LOGGER.debug("Sign in with ChatGPT returned: %s", error)
            return self._show_chatgpt_form(
                {"base": "access_denied" if error == "access_denied" else "unknown"}
            )

        if not params.get("code"):
            return self._show_chatgpt_form({"base": "invalid_callback_url"})

        if params.get("state") != request.state:
            return self._show_chatgpt_form({"base": "invalid_state"})

        if request.registration:
            # A new registration returns the issued client id, which replaces
            # `dynamic_agent_client` and is reused for later sign ins.
            client_id = params.get("client_id", "")
            if not client_id.startswith(CLIENT_ID_PREFIX):
                return self._show_chatgpt_form({"base": "registration_incomplete"})
        else:
            client_id = request.client_id
            if (returned := params.get("client_id")) and returned != client_id:
                return self._show_chatgpt_form({"base": "client_id_mismatch"})

        try:
            token = await async_token_request(
                self.hass,
                {
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "code": params["code"],
                    "code_verifier": request.code_verifier,
                    "redirect_uri": request.redirect_uri,
                    "resource": RESOURCE,
                },
            )
        except HomeAssistantError as err:
            _LOGGER.error("Sign in with ChatGPT failed: %s", err)
            return self._show_chatgpt_form({"base": "invalid_auth"})

        if PLAN_SCOPE not in str(token.get("scope", "")).split():
            # A valid sign in without the ChatGPT plan scope must not silently
            # fall back to an API key session.
            return self.async_abort(reason="plan_usage_not_granted")

        if not (id_token := token.get("id_token")):
            return self._show_chatgpt_form({"base": "invalid_auth"})

        try:
            claims = await async_validate_id_token(
                self.hass, id_token, client_id=client_id, nonce=request.nonce
            )
        except HomeAssistantError as err:
            _LOGGER.error("Sign in with ChatGPT returned an invalid ID token: %s", err)
            return self._show_chatgpt_form({"base": "invalid_auth"})

        credentials = credentials_from_token(
            token,
            client_id=client_id,
            ext_agent_host_id=request.ext_agent_host_id,
            sub=str(claims["sub"]),
            email=claims.get("email"),
        )
        data = credentials.as_entry_data()

        if entry is not None:
            if entry.data.get(CONF_SUB) not in (None, credentials.sub):
                # Reauthenticating with another ChatGPT account would replace
                # the entry while its unique id still names the old account.
                return self._show_chatgpt_form({"base": "wrong_account"})
            existing = self.hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, credentials.unique_id
            )
            if existing is not None and existing.entry_id != entry.entry_id:
                return self.async_abort(reason="already_configured")

            if not is_chatgpt_entry(entry):
                # Converting an API key entry to the plan: the plan usage route
                # has no speech to text or text to speech, and it rejects the
                # regular API default model.
                try:
                    model = await self._async_catalog_default(credentials)
                except HomeAssistantError as err:
                    _LOGGER.error("Could not list the ChatGPT plan models: %s", err)
                    return self._show_chatgpt_form({"base": "cannot_connect"})
                self._async_remove_speech_subentries(entry)
                if model is not None:
                    self._async_bind_catalog_model(entry, model)

            if entry.update_listeners:
                return self.async_update_and_abort(
                    entry, unique_id=credentials.unique_id, data=data
                )
            return self.async_update_reload_and_abort(
                entry, unique_id=credentials.unique_id, data=data
            )

        await self.async_set_unique_id(credentials.unique_id)
        self._abort_if_unique_id_configured()
        # The plan usage route rejects the regular API default model, so a new
        # entry must not be created before the user picked a model. The catalog
        # of the signed in account is offered when it can be read; when it
        # cannot, the user enters a model of their plan instead.
        self._siwc_credentials = credentials
        self._siwc_data = data
        self._siwc_models = await self._async_catalog_models(credentials)
        return await self.async_step_chatgpt_model()

    async def async_step_chatgpt_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which model a new ChatGPT plan entry should use.

        ChatGPT plan usage does not support speech to text, text to speech or
        image generation, and it serves its own catalog instead of the API
        default model, which it rejects. The catalog is offered as a dropdown;
        when it could not be read, the user enters a model instead.
        """
        if user_input is not None:
            model = user_input[CONF_CHAT_MODEL]
            return self.async_create_entry(
                title=DEFAULT_CHATGPT_TITLE,
                data=self._siwc_data,
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": {
                            **RECOMMENDED_CONVERSATION_OPTIONS,
                            CONF_CHAT_MODEL: model,
                        },
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    },
                    {
                        "subentry_type": "ai_task_data",
                        "data": {
                            **RECOMMENDED_AI_TASK_OPTIONS,
                            CONF_CHAT_MODEL: model,
                        },
                        "title": DEFAULT_AI_TASK_NAME,
                        "unique_id": None,
                    },
                ],
            )

        options = subscription_model_options(self._siwc_models)
        schema = probatio.Schema(
            {
                probatio.Required(CONF_CHAT_MODEL, default=options[0]): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="chatgpt_model", data_schema=schema)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        if is_chatgpt_entry(self._get_reauth_entry()):
            return await self.async_step_chatgpt()
        return await self.async_step_auth_method()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        return await self._async_step_api_key(user_input, "reauth_confirm")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the API key or the ChatGPT sign in."""
        if user_input is None:
            return await self.async_step_auth_method()
        return await self._async_step_api_key(user_input, "reconfigure")

    async def async_step_auth_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose the authentication method of the entry.

        Reauthentication and reconfiguration offer the same choice as adding
        the integration, so a broken API key entry can switch to the ChatGPT
        plan sign in in place, and a plan entry back to an API key.
        """
        if user_input is not None:
            if user_input.get(CONF_AUTH_METHOD) == AUTH_METHOD_CHATGPT:
                return await self.async_step_chatgpt()
            if self.source == SOURCE_REAUTH:
                return await self.async_step_reauth_confirm()
            return await self._async_step_api_key(None, "reconfigure")

        return self.async_show_form(
            step_id="auth_method",
            data_schema=STEP_AUTH_METHOD_DATA_SCHEMA,
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        subentry_types: dict[str, type[ConfigSubentryFlow]] = {
            "conversation": OpenAISubentryFlowHandler,
            "ai_task_data": OpenAISubentryFlowHandler,
        }
        if not is_chatgpt_entry(config_entry):
            # ChatGPT plan usage does not support speech to text or text to
            # speech, and the transcription API is not available.
            subentry_types["stt"] = OpenAISubentrySTTFlowHandler
            subentry_types["tts"] = OpenAISubentryTTSFlowHandler
        return subentry_types


class OpenAISubentryFlowHandler(ConfigSubentryFlow):
    """Flow for managing OpenAI subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        if self._subentry_type == "ai_task_data":
            self.options = RECOMMENDED_AI_TASK_OPTIONS.copy()
        else:
            self.options = RECOMMENDED_CONVERSATION_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        # abort if entry is not loaded
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options

        hass_apis: list[SelectOptionDict] = [
            SelectOptionDict(
                label=api.name,
                value=api.id,
            )
            for api in llm.async_get_apis(self.hass)
        ]
        if suggested_llm_apis := options.get(CONF_LLM_HASS_API):
            if isinstance(suggested_llm_apis, str):
                suggested_llm_apis = [suggested_llm_apis]
            valid_apis = {api.id for api in llm.async_get_apis(self.hass)}
            options[CONF_LLM_HASS_API] = [
                api for api in suggested_llm_apis if api in valid_apis
            ]

        step_schema: VolDictType = {}

        if self._is_new:
            if self._subentry_type == "ai_task_data":
                default_name = DEFAULT_AI_TASK_NAME
            else:
                default_name = DEFAULT_CONVERSATION_NAME
            step_schema[probatio.Required(CONF_NAME, default=default_name)] = str

        if self._subentry_type == "conversation":
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": options.get(
                                CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                            )
                        },
                    ): TemplateSelector(),
                    probatio.Optional(CONF_LLM_HASS_API): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                }
            )

        step_schema[
            probatio.Required(
                CONF_RECOMMENDED, default=options.get(CONF_RECOMMENDED, False)
            )
        ] = bool

        if user_input is not None:
            if user_input.get(CONF_LLM_HASS_API) is None:
                user_input.pop(CONF_LLM_HASS_API, None)

            if user_input[CONF_RECOMMENDED]:
                if self._is_new:
                    return self.async_create_entry(
                        title=user_input.pop(CONF_NAME),
                        data=user_input,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=user_input,
                )

            options.update(user_input)
            if CONF_LLM_HASS_API in options and CONF_LLM_HASS_API not in user_input:
                options.pop(CONF_LLM_HASS_API)
            return await self.async_step_additional()

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
        )

    async def async_step_additional(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage additional options."""
        options = self.options
        errors: dict[str, str] = {}

        # ChatGPT plan usage rejects the sampling and storage parameters. Its
        # chat model has to be one of the models of the account's catalog.
        subscription = is_chatgpt_entry(self._get_entry())

        catalog_models: list[str] = []
        catalog_available = False
        if subscription:
            try:
                catalog_models = await async_get_subscription_models(
                    self.hass,
                    ChatGPTAuth.from_entry(self.hass, self._get_entry()),
                )
                catalog_available = True
            except HomeAssistantError as err:
                # The catalog could not be read, which says nothing about the
                # model the user submits: it cannot be checked against the
                # catalog and is therefore accepted. The selector allows any
                # value to be typed.
                _LOGGER.warning("Could not read the OpenAI model catalog: %s", err)
            # The API default model is rejected by the plan usage route, so it
            # is only used as the default when the catalog could be read or a
            # model is already stored on the subentry.
            default = (
                catalog_models[0]
                if catalog_available
                else options.get(CONF_CHAT_MODEL)
                or subscription_model_options(catalog_models)[0]
            )
            step_schema: VolDictType = {
                (
                    probatio.Required(CONF_CHAT_MODEL, default=default)
                    if default
                    else probatio.Required(CONF_CHAT_MODEL)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=subscription_model_options(catalog_models),
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        else:
            step_schema = {
                probatio.Optional(
                    CONF_CHAT_MODEL,
                    default=RECOMMENDED_CHAT_MODEL,
                ): str,
            }
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_MAX_TOKENS,
                        default=RECOMMENDED_MAX_TOKENS,
                    ): int,
                    probatio.Optional(
                        CONF_TOP_P,
                        default=RECOMMENDED_TOP_P,
                    ): NumberSelector(NumberSelectorConfig(min=0, max=1, step=0.05)),
                    probatio.Optional(
                        CONF_TEMPERATURE,
                        default=RECOMMENDED_TEMPERATURE,
                    ): NumberSelector(NumberSelectorConfig(min=0, max=2, step=0.05)),
                    probatio.Optional(
                        CONF_STORE_RESPONSES,
                        default=RECOMMENDED_STORE_RESPONSES,
                    ): bool,
                }
            )

        if user_input is not None:
            options.update(user_input)
            if subscription:
                # Only a model the catalog actually offers is an error. When
                # the catalog could not be read it cannot be checked and the
                # submitted model is accepted.
                if (
                    catalog_available
                    and user_input.get(CONF_CHAT_MODEL) not in catalog_models
                ):
                    errors[CONF_CHAT_MODEL] = "model_not_supported"
            elif user_input.get(CONF_CHAT_MODEL) in UNSUPPORTED_MODELS:
                errors[CONF_CHAT_MODEL] = "model_not_supported"

            if not errors:
                return await self.async_step_model()

        return self.async_show_form(
            step_id="additional",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
            description_placeholders={
                "catalog_note": (
                    ""
                    if catalog_available or not subscription
                    else " The model catalog could not be read. Enter a model of "
                    "your ChatGPT plan, for example `gpt-5.5`."
                )
            },
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage model-specific options."""
        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        # ChatGPT plan usage does not support Code Interpreter, web search,
        # hosted tools or image generation.
        subscription = is_chatgpt_entry(self._get_entry())

        model = options[CONF_CHAT_MODEL]

        if not subscription and not model.startswith(
            tuple(UNSUPPORTED_CODE_INTERPRETER_MODELS)
        ):
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_CODE_INTERPRETER,
                        default=RECOMMENDED_CODE_INTERPRETER,
                    ): bool,
                }
            )
        elif CONF_CODE_INTERPRETER in options:
            options.pop(CONF_CODE_INTERPRETER)

        if reasoning_options := self._get_reasoning_options(model):
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_REASONING_EFFORT,
                        default=RECOMMENDED_REASONING_EFFORT,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=reasoning_options,
                            translation_key=CONF_REASONING_EFFORT,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_EFFORT in options:
            options.pop(CONF_REASONING_EFFORT)

        if model.startswith(("gpt-5.6", "gpt-6")):
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_PRO_MODE,
                        default=RECOMMENDED_PRO_MODE,
                    ): bool,
                }
            )
        elif CONF_PRO_MODE in options:
            options.pop(CONF_PRO_MODE)

        if model.startswith(("gpt-5", "gpt-6")):
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_VERBOSITY,
                        default=RECOMMENDED_VERBOSITY,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_VERBOSITY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_VERBOSITY in options:
            options.pop(CONF_VERBOSITY)

        if model.startswith(("o", "gpt-5", "gpt-6")):
            reasoning_summary_options = ["off", "auto", "concise", "detailed"]
            if model.startswith("o"):
                reasoning_summary_options.remove("concise")
            stored_summary = options.get(
                CONF_REASONING_SUMMARY, RECOMMENDED_REASONING_SUMMARY
            )
            if stored_summary not in reasoning_summary_options:
                stored_summary = RECOMMENDED_REASONING_SUMMARY
                options[CONF_REASONING_SUMMARY] = stored_summary
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_REASONING_SUMMARY,
                        default=stored_summary,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=reasoning_summary_options,
                            translation_key=CONF_REASONING_SUMMARY,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        elif CONF_REASONING_SUMMARY in options:
            options.pop(CONF_REASONING_SUMMARY)

        service_tiers = self._get_service_tiers(model)
        if "flex" in service_tiers or "priority" in service_tiers:
            step_schema[
                probatio.Optional(
                    CONF_SERVICE_TIER,
                    default=RECOMMENDED_SERVICE_TIER,
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=service_tiers,
                    translation_key=CONF_SERVICE_TIER,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            options.pop(CONF_SERVICE_TIER, None)
        if options.get(CONF_SERVICE_TIER) not in service_tiers:
            options.pop(CONF_SERVICE_TIER, None)

        if not subscription and not model.startswith(
            tuple(UNSUPPORTED_WEB_SEARCH_MODELS)
        ):
            step_schema.update(
                {
                    probatio.Optional(
                        CONF_WEB_SEARCH,
                        default=RECOMMENDED_WEB_SEARCH,
                    ): bool,
                    probatio.Optional(
                        CONF_WEB_SEARCH_CONTEXT_SIZE,
                        default=RECOMMENDED_WEB_SEARCH_CONTEXT_SIZE,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=["low", "medium", "high"],
                            translation_key=CONF_WEB_SEARCH_CONTEXT_SIZE,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    probatio.Optional(
                        CONF_WEB_SEARCH_USER_LOCATION,
                        default=RECOMMENDED_WEB_SEARCH_USER_LOCATION,
                    ): bool,
                    probatio.Optional(
                        CONF_WEB_SEARCH_INLINE_CITATIONS,
                        default=RECOMMENDED_WEB_SEARCH_INLINE_CITATIONS,
                    ): bool,
                }
            )
        elif CONF_WEB_SEARCH in options:
            options = {
                k: v
                for k, v in options.items()
                if k
                not in (
                    CONF_WEB_SEARCH,
                    CONF_WEB_SEARCH_CONTEXT_SIZE,
                    CONF_WEB_SEARCH_USER_LOCATION,
                    CONF_WEB_SEARCH_CITY,
                    CONF_WEB_SEARCH_REGION,
                    CONF_WEB_SEARCH_COUNTRY,
                    CONF_WEB_SEARCH_TIMEZONE,
                    CONF_WEB_SEARCH_INLINE_CITATIONS,
                )
            }

        if (
            not subscription
            and self._subentry_type == "ai_task_data"
            and not model.startswith(tuple(UNSUPPORTED_IMAGE_MODELS))
        ):
            step_schema[
                probatio.Optional(CONF_IMAGE_MODEL, default=RECOMMENDED_IMAGE_MODEL)
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[
                        "gpt-image-2.5-sunburst",
                        "gpt-image-2.5-flare",
                        "gpt-image-2",
                        "gpt-image-1.5",
                        "gpt-image-1",
                        "gpt-image-1-mini",
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        if user_input is not None:
            if user_input.get(CONF_WEB_SEARCH):
                if user_input.get(CONF_REASONING_EFFORT) == "minimal":
                    errors[CONF_WEB_SEARCH] = "web_search_minimal_reasoning"
                if user_input.get(CONF_WEB_SEARCH_USER_LOCATION) and not errors:
                    user_input.update(await self._get_location_data())
                else:
                    options.pop(CONF_WEB_SEARCH_CITY, None)
                    options.pop(CONF_WEB_SEARCH_REGION, None)
                    options.pop(CONF_WEB_SEARCH_COUNTRY, None)
                    options.pop(CONF_WEB_SEARCH_TIMEZONE, None)
            if (
                user_input.get(CONF_CODE_INTERPRETER)
                and user_input.get(CONF_REASONING_EFFORT) == "minimal"
            ):
                errors[CONF_CODE_INTERPRETER] = "code_interpreter_minimal_reasoning"

            options.update(user_input)
            if not errors:
                if self._is_new:
                    return self.async_create_entry(
                        title=options.pop(CONF_NAME),
                        data=options,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=options,
                )

        return self.async_show_form(
            step_id="model",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )

    def _get_reasoning_options(self, model: str) -> list[str]:
        """Get reasoning effort options based on model."""
        if not model.startswith(("o", "gpt-5", "gpt-6")) or model.startswith(
            "gpt-5-pro"
        ):
            return []

        models_reasoning_map: dict[str | tuple[str, ...], list[str]] = {
            "gpt-6-luna": ["none", "low", "medium", "high", "xhigh", "max"],
            "gpt-6": ["low", "medium", "high", "xhigh", "max"],
            "gpt-5.6": ["none", "low", "medium", "high", "xhigh", "max"],
            ("gpt-5.2-pro", "gpt-5.4-pro", "gpt-5.5-pro"): ["medium", "high", "xhigh"],
            ("gpt-5.2", "gpt-5.3", "gpt-5.4", "gpt-5.5"): [
                "none",
                "low",
                "medium",
                "high",
                "xhigh",
            ],
            "gpt-5.1": ["none", "low", "medium", "high"],
            "gpt-5": ["minimal", "low", "medium", "high"],
            "": ["low", "medium", "high"],  # The default case
        }

        for prefix, options in models_reasoning_map.items():
            if model.startswith(prefix):
                return options
        return []  # pragma: no cover

    def _get_service_tiers(self, model: str) -> list[str]:
        """Get service tier options based on model."""
        service_tiers = ["auto"]

        if not model.startswith(tuple(UNSUPPORTED_FLEX_SERVICE_TIERS_MODELS)):
            service_tiers.append("flex")

        service_tiers.append("default")

        if not model.startswith(tuple(UNSUPPORTED_PRIORITY_SERVICE_TIERS_MODELS)):
            service_tiers.append("priority")

        return service_tiers

    async def _get_location_data(self) -> dict[str, str]:
        """Get approximate location data of the user."""
        location_data: dict[str, str] = {}
        zone_home = self.hass.states.get(ENTITY_ID_HOME)
        if zone_home is not None:
            entry = self._get_entry()
            # Works for both API key and ChatGPT subscription entries, also
            # while the entry is not loaded.
            client: openai.AsyncClient
            if (runtime_data := getattr(entry, "runtime_data", None)) is not None:
                client = runtime_data
            elif is_chatgpt_entry(entry):  # pragma: no cover
                # Unreachable: a plan entry is never offered the web search
                # user location options, which are the only caller of this.
                client = ChatGPTSubscriptionClient(
                    ChatGPTAuth.from_entry(self.hass, entry),
                    http_client=get_async_client(self.hass),
                )
            else:
                client = openai.AsyncOpenAI(
                    api_key=entry.data[CONF_API_KEY],
                    http_client=get_async_client(self.hass),
                )
            location_schema = probatio.Schema(
                {
                    probatio.Optional(
                        CONF_WEB_SEARCH_CITY,
                        description=(
                            "Free text input for the city, e.g. `San Francisco`"
                        ),
                    ): str,
                    probatio.Optional(
                        CONF_WEB_SEARCH_REGION,
                        description="Free text input for the region, e.g. `California`",
                    ): str,
                }
            )
            response = await client.responses.create(
                model=RECOMMENDED_CHAT_MODEL,
                input=[
                    {
                        "role": "system",
                        "content": "Where are the following coordinates located: "
                        f"({zone_home.attributes[EntityStateAttribute.LATITUDE]},"
                        f" {zone_home.attributes[EntityStateAttribute.LONGITUDE]})?",
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "approximate_location",
                        "description": "Approximate location data of the user "
                        "for refined web search results",
                        "schema": probatio.to_openapi(
                            location_schema, openapi_version="3.1.0"
                        ),
                        "strict": False,
                    }
                },
                store=self.options.get(
                    CONF_STORE_RESPONSES, RECOMMENDED_STORE_RESPONSES
                ),
            )
            location_data = location_schema(json.loads(response.output_text) or {})

        if self.hass.config.country:
            location_data[CONF_WEB_SEARCH_COUNTRY] = self.hass.config.country
        location_data[CONF_WEB_SEARCH_TIMEZONE] = self.hass.config.time_zone

        _LOGGER.debug("Location data: %s", location_data)

        return location_data


class OpenAISubentrySTTFlowHandler(ConfigSubentryFlow):
    """Flow for managing OpenAI STT subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self.options = RECOMMENDED_STT_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        # abort if entry is not loaded
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[probatio.Required(CONF_NAME, default=DEFAULT_STT_NAME)] = str

        step_schema.update(
            {
                probatio.Optional(
                    CONF_PROMPT,
                    description={
                        "suggested_value": options.get(CONF_PROMPT, DEFAULT_STT_PROMPT)
                    },
                ): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                ),
                probatio.Optional(
                    CONF_CHAT_MODEL, default=RECOMMENDED_STT_MODEL
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            "gpt-4o-transcribe",
                            "gpt-4o-mini-transcribe",
                            "whisper-1",
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )

        if user_input is not None:
            options.update(user_input)
            if not errors:
                if self._is_new:
                    return self.async_create_entry(
                        title=options.pop(CONF_NAME),
                        data=options,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=options,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )


class OpenAISubentryTTSFlowHandler(ConfigSubentryFlow):
    """Flow for managing OpenAI TTS subentries."""

    options: dict[str, Any]

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a subentry."""
        self.options = RECOMMENDED_TTS_OPTIONS.copy()
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.options = self._get_reconfigure_subentry().data.copy()
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        # abort if entry is not loaded
        if self._get_entry().state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        options = self.options
        errors: dict[str, str] = {}

        step_schema: VolDictType = {}

        if self._is_new:
            step_schema[probatio.Required(CONF_NAME, default=DEFAULT_TTS_NAME)] = str

        step_schema.update(
            {
                probatio.Optional(CONF_PROMPT): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                ),
                probatio.Optional(
                    CONF_TTS_SPEED, default=RECOMMENDED_TTS_SPEED
                ): NumberSelector(NumberSelectorConfig(min=0.25, max=4.0, step=0.01)),
            }
        )

        if user_input is not None:
            options.update(user_input)
            if not errors:
                if self._is_new:
                    return self.async_create_entry(
                        title=options.pop(CONF_NAME),
                        data=options,
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=options,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(step_schema), options
            ),
            errors=errors,
        )
