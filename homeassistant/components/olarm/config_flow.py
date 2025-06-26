"""Config flow for olarm integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from olarmflowclient import OlarmFlowClient, OlarmFlowClientApiError
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_SOURCE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET

_LOGGER = logging.getLogger(__name__)


class OlarmOauth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Olarm using OAuth2."""

    DOMAIN = DOMAIN
    VERSION = 1

    _access_token: str | None = None
    _refresh_token: str | None = None
    _expires_at: int | None = None
    _user_id: str | None = None
    _devices: list[dict[str, Any]] | None = None
    _device_id: str | None = None
    _load_zones_bypass_entities: bool = False
    _oauth_data: dict[str, Any] | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_params(self) -> dict[str, str]:
        """Extra parameters for authorize. PKCE is handled automatically."""
        return {
            "scope": "email",
            "client_id": OAUTH2_CLIENT_ID,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        # Import the default client credential for public OAuth client
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Olarm"),
        )
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow, or update existing entry."""
        errors: dict[str, str] = {}

        if data["token"].get("access_token") is not None:
            self._oauth_data = data
            self._access_token = data["token"].get("access_token")
            self._refresh_token = data["token"].get("refresh_token")
            self._expires_at = data["token"].get("expires_at")

            _LOGGER.debug("OAuth2 tokens fetched successfully, fetching devices")
            if self._access_token is None:
                errors["base"] = "oauth_failed"
                return self.async_show_form(step_id="user", errors=errors)

            olarm_connect_client = OlarmFlowClient(self._access_token, self._expires_at)

            try:
                api_result = await olarm_connect_client.get_devices()
                _LOGGER.debug(api_result)

                self._devices = api_result.get("data")
                self._user_id = api_result.get("userId")
            except OlarmFlowClientApiError as err:
                # If the API returned a 404 or indicates nothing found, treat it as no devices
                err_str = str(err).lower()
                if "404" in err_str or "not found" in err_str:
                    return self.async_abort(reason="no_devices_found")

                # Otherwise, assume it's an auth-related error
                errors["base"] = "invalid_auth"
                return self.async_show_form(step_id="user", errors=errors)
            else:
                # Check if this is a reauth flow
                if self.context.get(CONF_SOURCE) == "reauth":
                    return await self.async_step_reauth_complete()
                return await self.async_step_device()
        else:
            # OAuth failed - no access token received
            errors["base"] = "oauth_failed"
            return self.async_show_form(step_id="user", errors=errors)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            _LOGGER.debug(user_input)
            self._device_id = user_input["select_device"]
            self._load_zones_bypass_entities = user_input.get(
                "load_zones_bypass", False
            )

            # abort if oauth data is not available
            if self._oauth_data is None:
                return self.async_abort(reason="oauth_data_missing")

            # load device details into config
            data = {
                "user_id": self._user_id,
                "device_id": self._device_id,
                "load_zones_bypass_entities": self._load_zones_bypass_entities,
                "auth_implementation": self._oauth_data["auth_implementation"],
                "token": self._oauth_data["token"],
            }

            # Create a unique ID using the device identifier
            unique_id = self._device_id
            await self.async_set_unique_id(unique_id)

            # Check if this exact configuration already exists
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title="Olarm Integration", data=data)

        # abort if no devices are found
        if self._devices is None:
            return self.async_abort(reason="no_devices_found")

        device_options: dict[str, str] = {
            device["deviceId"]: f"{device['deviceName']} - {device['deviceSerial']}"
            for device in self._devices
        }
        sorted_device_options = dict(
            sorted(device_options.items(), key=lambda item: item[1])
        )
        schema = vol.Schema(
            {
                vol.Required("select_device"): vol.In(sorted_device_options),
                vol.Optional(
                    "load_zones_bypass",
                    default=False,
                ): bool,
            },
        )

        return self.async_show_form(step_id="device", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")

        # Import the default client credential for public OAuth client
        await async_import_client_credential(
            self.hass,
            DOMAIN,
            ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Olarm"),
        )

        # Start the OAuth flow to get new tokens
        return await super().async_step_user()

    async def async_step_reauth_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Complete the reauthentication flow."""
        if self._oauth_data is None:
            return self.async_abort(reason="oauth_data_missing")

        # Get the existing config entry being reauthenticated
        reauth_entry_id = self.context.get("entry_id")
        if reauth_entry_id is None:
            return self.async_abort(reason="reauth_account_not_found")

        existing_entry = self.hass.config_entries.async_get_entry(reauth_entry_id)
        if existing_entry is None:
            return self.async_abort(reason="reauth_account_not_found")

        # Update the existing entry with new tokens, preserving existing device and user settings
        self.hass.config_entries.async_update_entry(
            existing_entry,
            data={
                **existing_entry.data,
                "token": self._oauth_data["token"],
                "auth_implementation": self._oauth_data["auth_implementation"],
                # Update user_id from API response but keep existing device configuration
                "user_id": self._user_id,
            },
        )

        # Reload the entry to use the new tokens
        await self.hass.config_entries.async_reload(existing_entry.entry_id)

        return self.async_abort(reason="reauth_successful")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
