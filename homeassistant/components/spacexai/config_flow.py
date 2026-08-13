"""Config flow for SpaceXAI."""

from collections.abc import Mapping
from logging import Logger
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntryState,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    ImplementationUnavailableError,
    async_get_implementations,
)
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
)
from homeassistant.loader import async_get_application_credentials

from . import (
    SpaceXAIConfigEntry,
    async_create_subscription_issue,
    async_mark_subscription_not_entitled,
    async_reconcile_snapshot,
)
from .client import ProviderSnapshot, SpaceXAIClient, StaticAccessTokenProvider
from .const import (
    CONF_MAX_OUTPUT_TOKENS,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DOMAIN,
    LOGGER,
)
from .errors import (
    AccountMismatchError,
    AuthenticationRejectedError,
    ConnectionFailureError,
    MalformedProviderResponseError,
    ModelNotEntitledError,
    NoConversationModelsError,
    QuotaLimitedError,
    RateLimitedError,
    ReauthenticationRequiredError,
    RefreshRejectedError,
    RequestTimeoutError,
    SpaceXAIError,
    SubscriptionNotEntitledError,
    TransientProviderError,
)


class SpaceXAIConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle SpaceXAI OAuth configuration."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._oauth_data: dict[str, Any] | None = None
        self._snapshot: ProviderSnapshot | None = None

    @property
    @override
    def logger(self) -> Logger:
        """Return the logger used by the OAuth flow."""
        return LOGGER

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start Authorization Code + PKCE once Application Credentials exist."""
        if err := await self._async_ensure_oauth_implementation():
            return err
        return await self.async_step_pick_implementation(user_input)

    async def _async_ensure_oauth_implementation(self) -> ConfigFlowResult | None:
        """Resolve Application Credentials into the active OAuth implementation."""
        try:
            implementations = await async_get_implementations(self.hass, self.DOMAIN)
        except ImplementationUnavailableError:
            return self.async_abort(reason="oauth_implementation_unavailable")
        if not implementations:
            if self.DOMAIN in await async_get_application_credentials(self.hass):
                return self.async_abort(reason="missing_credentials")
            return self.async_abort(reason="missing_configuration")
        self.flow_impl = next(iter(implementations.values()))
        return None

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an invalid OAuth session."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm that the user wants to sign in again."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Validate the OAuth account before creating an entry."""
        self._oauth_data = data
        return await self.async_step_validate()

    async def _async_refresh_snapshot(
        self, *, retry_step: str | None
    ) -> ConfigFlowResult | None:
        """Validate with the current OAuth token and store a fresh snapshot."""
        assert self._oauth_data is not None

        token_data = self._oauth_data.get("token")
        if (
            not isinstance(token_data, Mapping)
            or not isinstance(access_token := token_data.get("access_token"), str)
            or not access_token
            or not isinstance(token_data.get("refresh_token"), str)
            or not token_data["refresh_token"]
        ):
            return self.async_abort(reason="oauth_error")

        client = SpaceXAIClient(
            self.hass,
            StaticAccessTokenProvider(access_token),
            runtime_session=False,
        )
        expected_subject = (
            self._get_reauth_entry().unique_id if self.source == SOURCE_REAUTH else None
        )
        try:
            self._snapshot = await client.async_validate(
                expected_subject=expected_subject
            )
        except AccountMismatchError:
            return self.async_abort(reason="account_mismatch")
        except AuthenticationRejectedError:
            return self.async_abort(reason="oauth_unauthorized")
        except SubscriptionNotEntitledError:
            if self.source == SOURCE_REAUTH:
                entry = self._get_reauth_entry()
                if entry.state is ConfigEntryState.LOADED:
                    async_mark_subscription_not_entitled(self.hass, entry)
                else:
                    async_create_subscription_issue(self.hass, entry)
            return self.async_abort(reason="subscription_not_entitled")
        except NoConversationModelsError:
            return self.async_abort(reason="no_conversation_models")
        except ModelNotEntitledError:
            return self.async_abort(reason="model_not_entitled")
        except QuotaLimitedError:
            return self.async_abort(reason="quota_limited")
        except (
            ConnectionFailureError,
            RateLimitedError,
            RequestTimeoutError,
            TransientProviderError,
        ) as err:
            LOGGER.warning(
                "Unable to validate SpaceXAI account: category=%s operation=%s "
                "status=%s request_id=%s retryable=%s",
                err.category,
                err.context.operation,
                err.context.status,
                err.context.request_id,
                err.retryable,
            )
            if retry_step is None:
                return self.async_abort(reason="cannot_connect")
            return self.async_show_form(
                step_id=retry_step,
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )
        except MalformedProviderResponseError:
            return self.async_abort(reason="malformed_provider_response")
        except SpaceXAIError as err:
            LOGGER.warning(
                "Unexpected classified SpaceXAI setup failure: category=%s "
                "operation=%s status=%s request_id=%s retryable=%s",
                err.category,
                err.context.operation,
                err.context.status,
                err.context.request_id,
                err.retryable,
            )
            return self.async_abort(reason="unknown")
        return None

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate identity and available language models."""
        if err := await self._async_refresh_snapshot(retry_step="validate"):
            return err
        assert self._snapshot is not None
        assert self._oauth_data is not None

        await self.async_set_unique_id(self._snapshot.account.subject)
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="account_mismatch")
            entry = self._get_reauth_entry()
            result = self.async_update_and_abort(
                entry,
                data=self._oauth_data,
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return result

        self._abort_if_unique_id_configured()
        return await self.async_step_conversation()

    async def async_step_conversation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the initial Grok conversation entity."""
        assert self._snapshot is not None
        assert self._oauth_data is not None

        if user_input is not None:
            if err := await self._async_refresh_snapshot(retry_step=None):
                return err
            assert self._snapshot is not None
            if CONF_MODEL in user_input and not self._snapshot.has_model(
                user_input[CONF_MODEL]
            ):
                return self.async_abort(reason="model_not_entitled")
            return self.async_create_entry(
                title=self._snapshot.account.display_name,
                data=self._oauth_data,
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": user_input,
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    }
                ],
            )

        return self.async_show_form(
            step_id="conversation",
            data_schema=_conversation_schema(
                self._snapshot,
                _llm_api_options(self.hass),
                user_input,
            ),
        )

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: SpaceXAIConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry flow handlers."""
        return {"conversation": SpaceXAIConversationSubentryFlow}


class SpaceXAIConversationSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a SpaceXAI conversation entity."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a conversation subentry."""
        return await self._async_configure(user_input, is_new=True)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Reconfigure a conversation subentry."""
        return await self._async_configure(user_input, is_new=False)

    async def _async_configure(
        self,
        user_input: dict[str, Any] | None,
        *,
        is_new: bool,
    ) -> SubentryFlowResult:
        """Create or update a conversation subentry."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="entry_not_loaded")

        try:
            snapshot = await entry.runtime_data.client.async_validate(
                expected_subject=entry.unique_id
            )
        except (
            AccountMismatchError,
            AuthenticationRejectedError,
            ReauthenticationRequiredError,
            RefreshRejectedError,
        ):
            entry.async_start_reauth(self.hass)
            return self.async_abort(reason="oauth_unauthorized")
        except SubscriptionNotEntitledError:
            async_mark_subscription_not_entitled(self.hass, entry)
            return self.async_abort(reason="subscription_not_entitled")
        except NoConversationModelsError:
            return self.async_abort(reason="no_conversation_models")
        except QuotaLimitedError:
            return self.async_abort(reason="quota_limited")
        except ModelNotEntitledError:
            return self.async_abort(reason="model_not_entitled")
        except (
            ConnectionFailureError,
            RateLimitedError,
            RequestTimeoutError,
            TransientProviderError,
        ):
            return self.async_abort(reason="cannot_connect")
        except MalformedProviderResponseError:
            return self.async_abort(reason="malformed_provider_response")
        except SpaceXAIError:
            return self.async_abort(reason="unknown")

        async_reconcile_snapshot(self.hass, entry, snapshot)
        if user_input is not None:
            if CONF_MODEL in user_input and not snapshot.has_model(
                user_input[CONF_MODEL]
            ):
                return self.async_abort(reason="model_not_entitled")
            if is_new:
                return self.async_create_entry(
                    title=DEFAULT_CONVERSATION_NAME,
                    data=user_input,
                )
            return self.async_update_and_abort(
                entry,
                self._get_reconfigure_subentry(),
                data=user_input,
            )

        suggested = None if is_new else dict(self._get_reconfigure_subentry().data)
        return self.async_show_form(
            step_id="user" if is_new else "reconfigure",
            data_schema=_conversation_schema(
                snapshot,
                _llm_api_options(self.hass),
                user_input or suggested,
            ),
        )


def _model_selector_defaults(
    snapshot: ProviderSnapshot,
    suggested: Mapping[str, Any] | None,
) -> tuple[str, int, list[SelectOptionDict]]:
    """Return default model, token limit, and model options."""
    model_ids = {
        model_id for model in snapshot.models for model_id in model.selectable_ids
    }
    default_model = (
        DEFAULT_MODEL
        if DEFAULT_MODEL in model_ids
        else snapshot.models[0].selectable_ids[0]
    )
    suggested_max_tokens = DEFAULT_MAX_OUTPUT_TOKENS
    if suggested is not None:
        if (
            isinstance(suggested_model := suggested.get(CONF_MODEL), str)
            and suggested_model in model_ids
        ):
            default_model = suggested_model
        suggested_max_tokens = int(
            suggested.get(CONF_MAX_OUTPUT_TOKENS, DEFAULT_MAX_OUTPUT_TOKENS)
        )
    options = [
        SelectOptionDict(value=model_id, label=model_id)
        for model in snapshot.models
        for model_id in model.selectable_ids
    ]
    return default_model, suggested_max_tokens, options


def _conversation_schema(
    snapshot: ProviderSnapshot,
    llm_apis: list[SelectOptionDict],
    suggested: Mapping[str, Any] | None,
) -> vol.Schema:
    """Build the conversation configuration schema."""
    default_model, suggested_max_tokens, model_options = _model_selector_defaults(
        snapshot, suggested
    )
    available_api_ids = {option["value"] for option in llm_apis}
    if suggested is not None:
        if CONF_LLM_HASS_API in suggested:
            raw_apis = suggested[CONF_LLM_HASS_API]
            if isinstance(raw_apis, str):
                raw_apis = [raw_apis]
            if isinstance(raw_apis, list):
                suggested_apis = [
                    api_id for api_id in raw_apis if api_id in available_api_ids
                ]
            else:
                suggested_apis = []
        else:
            suggested_apis = []
        suggested_prompt = suggested.get(CONF_PROMPT)
    else:
        suggested_apis = [
            api_id for api_id in (llm.LLM_API_ASSIST,) if api_id in available_api_ids
        ]
        suggested_prompt = None

    return vol.Schema(
        {
            vol.Required(CONF_MODEL, default=default_model): SelectSelector(
                SelectSelectorConfig(options=model_options)
            ),
            vol.Optional(
                CONF_LLM_HASS_API,
                default=suggested_apis,
            ): SelectSelector(SelectSelectorConfig(options=llm_apis, multiple=True)),
            vol.Optional(
                CONF_PROMPT,
                description={"suggested_value": suggested_prompt},
            ): TemplateSelector(),
            **_max_output_tokens_schema(suggested_max_tokens),
        }
    )


def _max_output_tokens_schema(default: int) -> dict[Any, Any]:
    """Return the shared max-output-tokens field schema."""
    return {
        vol.Required(
            CONF_MAX_OUTPUT_TOKENS,
            default=default,
        ): vol.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=131072,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Coerce(int),
        )
    }


@callback
def _llm_api_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Return currently registered Home Assistant LLM APIs."""
    return [
        SelectOptionDict(value=api.id, label=api.name)
        for api in llm.async_get_apis(hass)
    ]
