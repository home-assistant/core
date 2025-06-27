"""PurpleAir config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiopurpleair import API
from aiopurpleair.errors import (
    InvalidApiKeyError,
    InvalidRequestError,
    NotFoundError,
    PurpleAirError,
    RequestError,
)
from aiopurpleair.models.keys import GetKeysResponse
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_BASE, CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import (
    CONF_ALREADY_CONFIGURED,
    CONF_INVALID_API_KEY,
    CONF_REAUTH_CONFIRM,
    CONF_REAUTH_SUCCESSFUL,
    CONF_RECONFIGURE,
    CONF_RECONFIGURE_SUCCESSFUL,
    CONF_SENSOR,
    CONF_UNKNOWN,
    DOMAIN,
    LOGGER,
    SCHEMA_VERSION,
    TITLE,
)
from .options_flow import PurpleAirOptionsFlow
from .subentry_flow import PurpleAirSubentryFlow


class PurpleAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = SCHEMA_VERSION

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}
        self._errors: dict[str, Any] = {}

    async def _async_get_title(self) -> str:
        """Get instance title."""
        title: str = TITLE
        config_list = self.hass.config_entries.async_loaded_entries(DOMAIN)
        if len(config_list) > 0:
            title = f"{TITLE} ({len(config_list)})"
        return title

    async def _async_validate_api_key(self) -> bool:
        """Validate API key."""
        self._errors = {}

        api = API(
            self._flow_data[CONF_API_KEY],
            session=aiohttp_client.async_get_clientsession(self.hass),
        )
        try:
            keys_response: GetKeysResponse = await api.async_check_api_key()
        except InvalidApiKeyError as err:
            LOGGER.exception("InvalidApiKeyError exception: %s", err)
            self._errors[CONF_API_KEY] = CONF_INVALID_API_KEY
            return False
        except (
            RequestError,
            InvalidRequestError,
            NotFoundError,
            PurpleAirError,
        ) as err:
            LOGGER.exception("PurpleAirError exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False
        except Exception as err:  # noqa: BLE001
            LOGGER.exception("Exception: %s", err)
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False

        if not keys_response:
            self._errors[CONF_BASE] = CONF_UNKNOWN
            return False

        if str(self._flow_data[CONF_API_KEY]) in (
            str(config_entry.data[CONF_API_KEY])
            for config_entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
        ):
            self._errors[CONF_API_KEY] = CONF_ALREADY_CONFIGURED
            return False

        return True

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Get config subentries."""
        return {
            CONF_SENSOR: PurpleAirSubentryFlow,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PurpleAirOptionsFlow:
        """Get options flow."""
        return PurpleAirOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initialization flow."""
        return await self.async_step_api_key(user_input)

    @property
    def api_key_schema(self) -> vol.Schema:
        """API key entry schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY, default=self._flow_data.get(CONF_API_KEY)
                ): cv.string,
            }
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle API key flow."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_API_KEY, data_schema=self.api_key_schema
            )

        self._flow_data[CONF_API_KEY] = str(user_input.get(CONF_API_KEY))
        if not await self._async_validate_api_key():
            return self.async_show_form(
                step_id=CONF_API_KEY,
                data_schema=self.api_key_schema,
                errors=self._errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=await self._async_get_title(),
            data={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            options={CONF_SHOW_ON_MAP: False},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    # Keep logic in sync with async_step_api_key()
    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth step."""
        if user_input is None:
            self._flow_data[CONF_API_KEY] = self._get_reauth_entry().data.get(
                CONF_API_KEY
            )
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = str(user_input[CONF_API_KEY])
        if not await self._async_validate_api_key():
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
                errors=self._errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_REAUTH_SUCCESSFUL,
        )

    # Keep logic in sync with async_step_api_key()
    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            self._flow_data[CONF_API_KEY] = self._get_reconfigure_entry().data.get(
                CONF_API_KEY
            )
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = str(user_input[CONF_API_KEY])
        if not await self._async_validate_api_key():
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
                errors=self._errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_RECONFIGURE_SUCCESSFUL,
        )
