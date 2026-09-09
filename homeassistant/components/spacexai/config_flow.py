"""Config flow for SpaceXAI."""

import asyncio
from typing import Any, override

from spacexai_subscription_client import (
    AuthenticationError,
    AuthorizationDeniedError,
    ConnectionFailureError,
    DeviceAuthorization,
    DeviceAuthorizationExpiredError,
    OAuthToken,
    PermissionDeniedError,
    RateLimitError,
    RequestTimeoutError,
    SpaceXAISubscriptionClient,
    SpaceXAISubscriptionError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LLM_HASS_API, CONF_MODEL, CONF_PROMPT
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TemplateSelector,
)

from . import create_client
from .const import DEFAULT_CONVERSATION_NAME, DOMAIN, RECOMMENDED_CONVERSATION_OPTIONS


class SpaceXAIConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle SpaceXAI configuration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._client: SpaceXAISubscriptionClient | None = None
        self._device: DeviceAuthorization | None = None
        self._login_task: asyncio.Task[OAuthToken] | None = None
        self._token: dict[str, Any] | None = None
        self._account_name = "SpaceXAI"
        self._models: list[str] = []

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start device authorization."""
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authorize with SpaceXAI using a device code."""
        if self._device is None:
            try:
                self._client = create_client(self.hass)
                self._device = await self._client.async_request_device_authorization()
            except AuthenticationError:
                return self.async_abort(reason="invalid_auth")
            except PermissionDeniedError:
                return self.async_abort(reason="not_entitled")
            except SpaceXAISubscriptionError:
                return await self.async_step_device_connection_error()

        if self._login_task is None:
            assert self._client is not None
            self._login_task = self.hass.async_create_background_task(
                self._client.async_poll_device_token(self._device),
                "SpaceXAI device authorization",
            )

        if self._login_task.done():
            login_task = self._login_task
            self._login_task = None
            if error := login_task.exception():
                if isinstance(error, AuthorizationDeniedError):
                    self._device = None
                    return self.async_show_progress_done(next_step_id="device_denied")
                if isinstance(error, AuthenticationError):
                    self._device = None
                    return self.async_show_progress_done(
                        next_step_id="device_invalid_auth"
                    )
                if isinstance(error, PermissionDeniedError):
                    self._device = None
                    return self.async_show_progress_done(
                        next_step_id="device_not_entitled"
                    )
                if isinstance(error, DeviceAuthorizationExpiredError):
                    self._device = None
                    return self.async_show_progress_done(next_step_id="device_timeout")
                if not isinstance(
                    error,
                    (ConnectionFailureError, RateLimitError, RequestTimeoutError),
                ):
                    self._device = None
                return self.async_show_progress_done(
                    next_step_id="device_connection_error"
                )
            self._token = login_task.result().as_dict()
            self._device = None
            return self.async_show_progress_done(next_step_id="device_finish")

        return self.async_show_progress(
            step_id="device",
            progress_action="wait_for_device",
            description_placeholders={
                "user_code": self._device.user_code,
                "verification_uri": self._device.verification_uri_complete,
            },
            progress_task=self._login_task,
        )

    async def async_step_device_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the OAuth account after device approval."""
        assert self._token is not None
        try:
            await self._async_validate_account()
        except AuthenticationError:
            return self.async_abort(reason="invalid_auth")
        except PermissionDeniedError:
            return self.async_abort(reason="not_entitled")
        except SpaceXAISubscriptionError:
            return await self.async_step_device_validation_error()

        return await self.async_step_conversation()

    async def async_step_conversation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the initial conversation agent."""
        assert self._token is not None
        if user_input is not None:
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            return self.async_create_entry(
                title=self._account_name,
                data={"auth_implementation": DOMAIN, "token": self._token},
                subentries=[
                    {
                        "subentry_type": "conversation",
                        "data": user_input,
                        "title": DEFAULT_CONVERSATION_NAME,
                        "unique_id": None,
                    }
                ],
            )

        hass_apis = [
            SelectOptionDict(label=api.name, value=api.id)
            for api in llm.async_get_apis(self.hass)
        ]
        return self.async_show_form(
            step_id="conversation",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODEL): SelectSelector(
                        SelectSelectorConfig(
                            options=self._models,
                            mode=SelectSelectorMode.DROPDOWN,
                            sort=True,
                        )
                    ),
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": RECOMMENDED_CONVERSATION_OPTIONS[
                                CONF_PROMPT
                            ]
                        },
                    ): TemplateSelector(),
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        default=RECOMMENDED_CONVERSATION_OPTIONS[CONF_LLM_HASS_API],
                    ): SelectSelector(
                        SelectSelectorConfig(options=hass_apis, multiple=True)
                    ),
                }
            ),
        )

    async def async_step_device_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry after the device code expires."""
        if user_input is None:
            return self.async_show_form(step_id="device_timeout")
        return await self.async_step_device()

    async def async_step_device_denied(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry after device authorization is denied."""
        if user_input is None:
            return self.async_show_form(step_id="device_denied")
        return await self.async_step_device()

    async def async_step_device_invalid_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort after device authorization credentials are rejected."""
        return self.async_abort(reason="invalid_auth")

    async def async_step_device_not_entitled(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when the account cannot use the subscription API."""
        return self.async_abort(reason="not_entitled")

    async def async_step_device_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry after a device authorization connection error."""
        if user_input is None:
            return self.async_show_form(step_id="device_connection_error")
        return await self.async_step_device()

    async def async_step_device_validation_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry after account validation fails."""
        if user_input is None:
            return self.async_show_form(step_id="device_validation_error")
        return await self.async_step_device_finish()

    async def _async_validate_account(self) -> None:
        """Validate account identity and load available models."""
        assert self._token is not None
        assert self._client is not None
        access_token = self._token["access_token"]
        account = await self._client.async_get_account(access_token)
        await self.async_set_unique_id(account.subject)
        self._abort_if_unique_id_configured()
        self._account_name = account.display_name
        self._models = list(await self._client.async_list_models(access_token))
        if not self._models:
            raise SpaceXAISubscriptionError
