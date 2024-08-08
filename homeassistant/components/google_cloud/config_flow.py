"""Config flow for the Google Cloud integration."""

from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from typing import TYPE_CHECKING, Any, cast

from google.cloud import texttospeech
import voluptuous as vol

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.tts import CONF_LANG
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    FileSelector,
    FileSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_KEY_FILE, CONF_SERVICE_ACCOUNT_INFO, DEFAULT_LANG, DOMAIN, TITLE
from .helpers import (
    async_tts_voices,
    tts_options_schema,
    tts_platform_schema,
    validate_service_account_info,
)

_LOGGER = logging.getLogger(__name__)

UPLOADED_KEY_FILE = "uploaded_key_file"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(UPLOADED_KEY_FILE): FileSelector(
            FileSelectorConfig(accept=".json,application/json")
        )
    }
)


class GoogleCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Cloud integration."""

    VERSION = 1

    _name: str | None = None

    def __init__(self) -> None:
        """Initialize a new GoogleCloudConfigFlow."""
        self.entry: ConfigEntry | None = None
        self.abort_reason: str | None = None

    def _parse_uploaded_file(self, uploaded_file_id: str) -> dict[str, Any]:
        """Read and parse an uploaded JSON file."""
        with process_uploaded_file(self.hass, uploaded_file_id) as file_path:
            contents = file_path.read_text()
        return cast(dict[str, Any], json.loads(contents))

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, Any] = {}
        if user_input is not None:
            try:
                service_account_info = await self.hass.async_add_executor_job(
                    self._parse_uploaded_file, user_input[UPLOADED_KEY_FILE]
                )
                validate_service_account_info(service_account_info)
            except ValueError:
                _LOGGER.exception("Reading uploaded JSON file failed")
                errors["base"] = "invalid_file"
            else:
                data = {CONF_SERVICE_ACCOUNT_INFO: service_account_info}
                if self.entry:
                    if TYPE_CHECKING:
                        assert self.abort_reason
                    return self.async_update_reload_and_abort(
                        self.entry, data=data, reason=self.abort_reason
                    )
                return self.async_create_entry(title=TITLE, data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "url": "https://console.cloud.google.com/apis/credentials/serviceaccountkey"
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.abort_reason = "reauth_successful"
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is not None:
            return await self.async_step_user()
        if TYPE_CHECKING:
            assert self.entry
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={CONF_NAME: self.entry.title},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        self.abort_reason = "reconfigure_successful"
        if TYPE_CHECKING:
            assert self.entry
        return await self.async_step_user()

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import Google Cloud configuration from YAML."""

        def _read_key_file() -> dict[str, Any]:
            with open(
                self.hass.config.path(import_data[CONF_KEY_FILE]), encoding="utf8"
            ) as f:
                return cast(dict[str, Any], json.load(f))

        service_account_info = await self.hass.async_add_executor_job(_read_key_file)
        try:
            validate_service_account_info(service_account_info)
        except ValueError:
            _LOGGER.exception("Reading credentials JSON file failed")
            return self.async_abort(reason="invalid_file")
        options = {
            k: v for k, v in import_data.items() if k in tts_platform_schema().schema
        }
        options.pop(CONF_KEY_FILE)
        _LOGGER.info("Creating imported config entry with options: %s", options)
        return self.async_create_entry(
            title=TITLE,
            data={CONF_SERVICE_ACCOUNT_INFO: service_account_info},
            options=options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoogleCloudOptionsFlowHandler:
        """Create the options flow."""
        return GoogleCloudOptionsFlowHandler(config_entry)


class GoogleCloudOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Google Cloud options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        service_account_info = self.config_entry.data[CONF_SERVICE_ACCOUNT_INFO]
        client: texttospeech.TextToSpeechAsyncClient = (
            texttospeech.TextToSpeechAsyncClient.from_service_account_info(
                service_account_info
            )
        )
        voices = await async_tts_voices(client)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LANG,
                        description={"suggested_value": self.options.get(CONF_LANG)},
                        default=DEFAULT_LANG,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN, options=list(voices)
                        )
                    ),
                    **tts_options_schema(self.options, voices, True).schema,
                }
            ),
        )
