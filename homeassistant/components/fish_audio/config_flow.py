"""Config flow for the Fish Audio integration."""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
import logging
from typing import Any, cast

from fish_audio_sdk import Session
from fish_audio_sdk.exceptions import HttpCodeErr
from fish_audio_sdk.schemas import APICreditEntity

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.selector import SelectOptionDict

from .const import (
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_USER_ID,
    CONF_VOICE_ID,
    DOMAIN,
)
from .error import (
    CannotConnectError,
    CannotGetModelsError,
    InvalidAuthError,
    UnexpectedError,
)
from .schemas import get_api_key_schema, get_filter_schema, get_model_selection_schema
from .types import SubentryInitUserInput, SubentryModelUserInput, TTSConfigData

_LOGGER = logging.getLogger(__name__)


class FishAudioConfigFlowManager:
    """Manage the configuration flow for Fish Audio."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass
        self.session: Session

    def init_session(self, session: Session) -> None:
        """Initialize the session."""
        self.session = session

    async def validate_api_key(self, api_key: str) -> APICreditEntity:
        """Validate the user input allows us to connect."""
        session = Session(api_key)

        try:
            credit_info = await self.hass.async_add_executor_job(session.get_api_credit)
        except HttpCodeErr as exc:
            if exc.status == 401:
                raise InvalidAuthError(exc) from exc
            raise CannotConnectError(exc) from exc
        except Exception as exc:
            raise UnexpectedError(exc) from exc

        self.init_session(session)

        return credit_info

    async def async_get_models(
        self, self_only: bool, language: str | None, sort_by: str
    ) -> list[SelectOptionDict]:
        """Get the available models."""
        try:
            func = partial(
                self.session.list_models,
                self_only=self_only,
                language=language,
                sort_by=sort_by,
            )
            models_response = await self.hass.async_add_executor_job(func)
            models = models_response.items
        except Exception as exc:
            raise CannotGetModelsError(exc) from exc

        return [
            SelectOptionDict(value=model.id, label=model.title)
            for model in sorted(models, key=lambda m: m.title)
        ]

    def show_api_key_form(
        self,
        handler: ConfigFlow,
        errors: dict[str, str] | None = None,
        default: str | None = None,
    ) -> ConfigFlowResult:
        """Show the API key form."""
        return handler.async_show_form(
            step_id="user",
            data_schema=get_api_key_schema(default=default),
            errors=errors or {},
        )

    def show_reauth_form(
        self,
        handler: ConfigFlow,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the reauth form."""
        return handler.async_show_form(
            step_id="reauth_confirm",
            data_schema=get_api_key_schema(),
            description_placeholders=None,
            errors=errors or {},
        )

    def show_reconfigure_form(
        self,
        handler: ConfigFlow,
        errors: dict[str, str] | None = None,
        default: str | None = None,
    ) -> ConfigFlowResult:
        """Show the reconfigure form."""
        return handler.async_show_form(
            step_id="reconfigure",
            data_schema=get_api_key_schema(default=default),
            errors=errors or {},
        )

    def show_filter_form(
        self,
        handler: FishAudioSubentryFlowHandler,
        errors: dict[str, str] | None = None,
    ) -> SubentryFlowResult:
        """Show the filter form."""
        return handler.async_show_form(
            step_id="init",
            data_schema=get_filter_schema(handler.config_data),
            errors=errors or {},
        )

    async def show_model_form(
        self,
        handler: FishAudioSubentryFlowHandler,
        errors: dict[str, str] | None = None,
    ) -> SubentryFlowResult:
        """Show the model selection form."""
        try:
            models = await self.async_get_models(
                self_only=cast(bool, handler.config_data.get(CONF_SELF_ONLY, False)),
                language=cast(str | None, handler.config_data.get(CONF_LANGUAGE)),
                sort_by=cast(str, handler.config_data.get(CONF_SORT_BY, "score")),
            )
        except CannotGetModelsError:
            models = []

        form_errors = errors or {}
        if not models:
            form_errors["base"] = "no_models_found"

        handler.models = models

        return handler.async_show_form(
            step_id="model",
            data_schema=get_model_selection_schema(handler.config_data, models),
            errors=form_errors,
        )


class FishAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fish Audio."""

    VERSION = 1
    manager: FishAudioConfigFlowManager
    _reauth_entry: ConfigEntry | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry = None

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        errors: dict[str, str] = {}
        self.manager = FishAudioConfigFlowManager(self.hass)

        if user_input:
            try:
                credit_info = await self.manager.validate_api_key(
                    user_input[CONF_API_KEY]
                )
                if credit_info.user_id != entry.data[CONF_USER_ID]:
                    errors["base"] = "reconfigure_wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                        reason="reconfigure_successful",
                    )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except UnexpectedError:
                errors["base"] = "unknown"

        return self.manager.show_reconfigure_form(
            self, errors=errors, default=entry.data.get(CONF_API_KEY)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.manager = FishAudioConfigFlowManager(self.hass)
        if user_input is None:
            return self.manager.show_api_key_form(self)

        errors: dict[str, str] = {}

        try:
            credit_info = await self.manager.validate_api_key(user_input[CONF_API_KEY])
            await self.async_set_unique_id(credit_info.user_id)
            self._abort_if_unique_id_configured()

            data: dict[str, Any] = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_USER_ID: credit_info.user_id,
            }

            return self.async_create_entry(
                title="Fish Audio",
                data=data,
            )

        except AbortFlow:
            raise
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        except UnexpectedError:
            errors["base"] = "unknown"

        return self.manager.show_api_key_form(self, errors=errors)

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        manager = FishAudioConfigFlowManager(self.hass)

        if user_input:
            assert self._reauth_entry
            try:
                credit_info = await manager.validate_api_key(user_input[CONF_API_KEY])
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
                if self._reauth_entry.unique_id != credit_info.user_id:
                    await self.async_set_unique_id(credit_info.user_id)
                    self._abort_if_unique_id_configured()

                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

            except AbortFlow:
                raise
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except UnexpectedError:
                errors["base"] = "unknown"

        return manager.show_reauth_form(self, errors=errors)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry) -> dict[str, type]:
        """Return subentries supported by this integration."""
        return {"tts": FishAudioSubentryFlowHandler}


class FishAudioSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a tts entity."""

    config_data: TTSConfigData
    manager: FishAudioConfigFlowManager
    models: list[SelectOptionDict] = []

    @property
    def _is_new(self) -> bool:
        """Return if this is a new subentry."""
        return self.source == "user"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the initial step."""
        self.config_data = {}
        return await self.async_step_init()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle reconfiguration of a subentry."""
        self.config_data = cast(
            TTSConfigData, dict(self._get_reconfigure_subentry().data)
        )
        return await self.async_step_init()

    async def async_step_init(
        self, user_input: SubentryInitUserInput | None = None
    ) -> SubentryFlowResult:
        """Manage initial options."""
        self.manager = FishAudioConfigFlowManager(self.hass)
        try:
            await self.manager.validate_api_key(self._get_entry().data[CONF_API_KEY])
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_model()

        return self.manager.show_filter_form(self)

    async def async_step_model(
        self, user_input: SubentryModelUserInput | None = None
    ) -> SubentryFlowResult:
        """Handle the model selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if (voice_id := user_input.get(CONF_VOICE_ID)) and (
                backend := user_input.get(CONF_BACKEND)
            ):
                self.config_data.update(user_input)
                if self._is_new:
                    voice_name = next(
                        (m["label"] for m in self.models if m["value"] == voice_id),
                        "Fish Audio TTS",
                    )
                    unique_id = f"{voice_id}-{backend}"

                    return self.async_create_entry(
                        title=voice_name, data=self.config_data, unique_id=unique_id
                    )
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=self.config_data,
                )
            errors["base"] = "no_model_selected"

        return await self.manager.show_model_form(self, errors=errors)
