"""Config flow for the Fish Audio integration."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any, TypedDict, cast

from fish_audio_sdk import Session
from fish_audio_sdk.exceptions import HttpCodeErr
from fish_audio_sdk.schemas import APICreditEntity
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BACKEND_MODELS,
    CONF_API_KEY,
    CONF_BACKEND,
    CONF_LANGUAGE,
    CONF_NAME,
    CONF_SELF_ONLY,
    CONF_SORT_BY,
    CONF_USER_ID,
    CONF_VOICE_ID,
    DOMAIN,
    SIGNUP_URL,
    SORT_BY_OPTIONS,
    TTS_SUPPORTED_LANGUAGES,
)
from .error import (
    CannotConnectError,
    CannotGetModelsError,
    InvalidAuthError,
    UnexpectedError,
)

_LOGGER = logging.getLogger(__name__)


class TTSConfigData(TypedDict, total=False):
    """Fish Audio TTS subentry configuration data."""

    voice_id: str
    backend: str
    language: str
    self_only: bool
    sort_by: str
    name: str


class SubentryInitUserInput(TypedDict, total=False):
    """User input for the Fish Audio subentry init step."""

    name: str
    language: str
    self_only: bool
    sort_by: str


class SubentryModelUserInput(TypedDict):
    """User input for the Fish Audio subentry model step."""

    voice_id: str
    backend: str


class SubentryNameUserInput(TypedDict):
    """User input for the Fish Audio subentry name step."""

    name: str


def get_api_key_schema(default: str | None = None) -> vol.Schema:
    """Return the schema for API key input."""
    return vol.Schema(
        {vol.Required(CONF_API_KEY, default=default or vol.UNDEFINED): str}
    )


def get_filter_schema(options: TTSConfigData) -> vol.Schema:
    """Return the schema for the filter step."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_SELF_ONLY, default=options.get(CONF_SELF_ONLY, False)
            ): bool,
            vol.Optional(
                CONF_LANGUAGE, default=options.get(CONF_LANGUAGE, "en")
            ): LanguageSelector(
                LanguageSelectorConfig(
                    languages=TTS_SUPPORTED_LANGUAGES,
                )
            ),
            vol.Optional(
                CONF_SORT_BY, default=options.get(CONF_SORT_BY, "score")
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SORT_BY_OPTIONS, mode=SelectSelectorMode.DROPDOWN
                )
            ),
        }
    )


def get_model_selection_schema(
    options: TTSConfigData, model_options: list[SelectOptionDict]
) -> vol.Schema:
    """Return the schema for the model selection step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_VOICE_ID,
                default=options.get(CONF_VOICE_ID, ""),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=model_options,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                    sort=True,
                )
            ),
            vol.Required(
                CONF_BACKEND,
                default=options.get(CONF_BACKEND, "s1"),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=opt, label=opt) for opt in BACKEND_MODELS
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


def get_name_schema(options: TTSConfigData, default: str | None = None) -> vol.Schema:
    """Return the schema for the name input."""
    return vol.Schema({vol.Required(CONF_NAME, default=default or vol.UNDEFINED): str})


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
    session: Session | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.session = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=get_api_key_schema(),
                errors={},
                description_placeholders={"signup_url": SIGNUP_URL},
            )

        errors: dict[str, str] = {}

        try:
            credit_info, self.session = await _validate_api_key(
                self.hass, user_input[CONF_API_KEY]
            )
        except InvalidAuthError:
            errors["base"] = "invalid_auth"
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        except UnexpectedError:
            errors["base"] = "unknown"
        else:
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

        return self.async_show_form(
            step_id="user",
            data_schema=get_api_key_schema(),
            errors=errors,
            description_placeholders={"signup_url": SIGNUP_URL},
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type]:
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
        func = partial(
            self.session.list_models,
            self_only=self_only,
            language=language,
            sort_by=sort_by,
        )
        try:
            models_response = await self.hass.async_add_executor_job(func)
        except Exception as exc:
            raise CannotGetModelsError(exc) from exc
        models = models_response.items

        return [SelectOptionDict(value=model.id, label=model.title) for model in models]

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
        api_key = self._get_entry().data[CONF_API_KEY]
        try:
            _, self.session = await _validate_api_key(self.hass, api_key)
        except InvalidAuthError:
            return self.async_abort(reason="invalid_auth")
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")
        except UnexpectedError:
            return self.async_abort(reason="unknown")

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
