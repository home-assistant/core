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
    CONF_NAME,
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
from .schemas import (
    get_api_key_schema,
    get_filter_schema,
    get_model_selection_schema,
    get_name_schema,
)
from .types import (
    SubentryInitUserInput,
    SubentryModelUserInput,
    SubentryNameUserInput,
    TTSConfigData,
    UserInput,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_api_key(
    hass: HomeAssistant, api_key: str
) -> tuple[APICreditEntity, Session]:
    """Validate the user input allows us to connect."""
    session = Session(api_key)

    try:
        credit_info = await hass.async_add_executor_job(session.get_api_credit)
    except HttpCodeErr as exc:
        if exc.status == 401:
            raise InvalidAuthError(exc) from exc
        raise CannotConnectError(exc) from exc
    except Exception as exc:
        raise UnexpectedError(exc) from exc

    return credit_info, session


class FishAudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fish Audio."""

    VERSION = 1
    _reauth_entry: ConfigEntry | None
    session: Session | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry = None
        self.session = None

    async def async_step_reconfigure(
        self, user_input: UserInput | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry

        errors: dict[str, str] = {}

        if user_input:
            try:
                credit_info, _ = await _validate_api_key(
                    self.hass, user_input[CONF_API_KEY]
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

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_api_key_schema(default=entry.data.get(CONF_API_KEY)),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=get_api_key_schema(), errors={}
            )

        errors: dict[str, str] = {}

        try:
            credit_info, self.session = await _validate_api_key(
                self.hass, user_input[CONF_API_KEY]
            )
            await self.async_set_unique_id(credit_info.user_id)
            self._abort_if_unique_id_configured()
        except AbortFlow:
            raise
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        except UnexpectedError:
            errors["base"] = "unknown"
        else:
            data: dict[str, Any] = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_USER_ID: credit_info.user_id,
            }

            return self.async_create_entry(
                title="Fish Audio",
                data=data,
            )

        return self.async_show_form(
            step_id="user", data_schema=get_api_key_schema(), errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: UserInput | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input:
            assert self._reauth_entry
            try:
                credit_info, _ = await _validate_api_key(
                    self.hass, user_input[CONF_API_KEY]
                )
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

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=get_api_key_schema(), errors=errors
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry) -> dict[str, type]:
        """Return subentries supported by this integration."""
        return {"tts": FishAudioSubentryFlowHandler}


class FishAudioSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flow for adding and modifying a tts entity."""

    config_data: TTSConfigData
    models: list[SelectOptionDict]
    session: Session

    def __init__(self) -> None:
        """Initialize the subentry flow handler."""
        super().__init__()
        self.models = []

    async def _async_get_models(
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
        try:
            self.session = Session(self._get_entry().data[CONF_API_KEY])
            await self.hass.async_add_executor_job(self.session.get_api_credit)
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_model()

        return self.async_show_form(
            step_id="init",
            data_schema=get_filter_schema(self.config_data),
            errors={},
        )

    async def async_step_model(
        self, user_input: SubentryModelUserInput | None = None
    ) -> SubentryFlowResult:
        """Handle the model selection step."""
        errors: dict[str, str] = {}

        if not self.models:
            try:
                self.models = await self._async_get_models(
                    self_only=self.config_data.get(CONF_SELF_ONLY, False),
                    language=self.config_data.get(CONF_LANGUAGE),
                    sort_by=self.config_data.get(CONF_SORT_BY, "score"),
                )
            except CannotGetModelsError:
                self.models = []

            if not self.models:
                errors["base"] = "no_models_found"

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

                    return await self.async_step_name(default=voice_name)

                unique_id = f"{voice_id}-{backend}"

                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    data=self.config_data,
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="model",
            data_schema=get_model_selection_schema(self.config_data, self.models),
            errors=errors,
        )

    async def async_step_name(
        self,
        user_input: SubentryNameUserInput | None = None,
        default: str | None = None,
        unique_id: str | None = None,
    ) -> SubentryFlowResult:
        """Handle the name selection step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.config_data.update(user_input)
            unique_id = (
                f"{self.config_data[CONF_VOICE_ID]}-{self.config_data[CONF_BACKEND]}"
            )
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=self.config_data,
                unique_id=unique_id,
            )
        return self.async_show_form(
            step_id="name",
            data_schema=get_name_schema(self.config_data, default),
            errors=errors,
        )
