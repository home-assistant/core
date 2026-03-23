"""Config flow for Threema Gateway integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import (
    ThreemaAPIClient,
    ThreemaAuthError,
    ThreemaConnectionError,
    generate_key_pair,
)
from .const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    CONF_PUBLIC_KEY,
    CONF_RECIPIENT,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)

_LOGGER = logging.getLogger(__name__)


class ThreemaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Threema Gateway."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {SUBENTRY_TYPE_RECIPIENT: RecipientSubentryFlowHandler}

    _gateway_id: str | None = None
    _api_secret: str | None = None
    _private_key: str | None = None
    _public_key: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - choose setup type."""
        if user_input is not None:
            if user_input.get("setup_type") == "new":
                return await self.async_step_setup_new()
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_type", default="existing"): vol.In(
                        ["existing", "new"]
                    ),
                }
            ),
        )

    async def async_step_setup_new(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Generate keys for a new Gateway ID."""
        if user_input is not None:
            if user_input.get(CONF_PRIVATE_KEY):
                self._private_key = user_input[CONF_PRIVATE_KEY]
            if user_input.get(CONF_PUBLIC_KEY):
                self._public_key = user_input[CONF_PUBLIC_KEY]
            return await self.async_step_credentials()

        try:
            private_key, public_key = await self.hass.async_add_executor_job(
                generate_key_pair
            )
            self._private_key = private_key
            self._public_key = public_key
        except Exception:
            _LOGGER.exception("Failed to generate key pair")
            return self.async_abort(reason="key_generation_failed")

        return self.async_show_form(
            step_id="setup_new",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PUBLIC_KEY, default=public_key): str,
                    vol.Optional(CONF_PRIVATE_KEY, default=private_key): str,
                }
            ),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect Gateway credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            gateway_id = user_input[CONF_GATEWAY_ID].strip().upper()

            if not gateway_id.startswith("*") or len(gateway_id) != 8:
                errors["base"] = "invalid_gateway_id"
            else:
                await self.async_set_unique_id(gateway_id)
                self._abort_if_unique_id_configured()

                self._gateway_id = gateway_id
                self._api_secret = user_input[CONF_API_SECRET].strip()

                private_key = user_input.get(CONF_PRIVATE_KEY, "").strip() or None
                if private_key:
                    self._private_key = private_key
                public_key = user_input.get(CONF_PUBLIC_KEY, "").strip() or None
                if public_key:
                    self._public_key = public_key

                client = ThreemaAPIClient(
                    self.hass,
                    gateway_id=gateway_id,
                    api_secret=self._api_secret,
                    private_key=self._private_key,
                )

                try:
                    await client.validate_credentials()
                except ThreemaAuthError:
                    errors["base"] = "invalid_auth"
                except ThreemaConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating credentials")
                    errors["base"] = "unknown"
                else:
                    data: dict[str, str] = {
                        CONF_GATEWAY_ID: self._gateway_id,
                        CONF_API_SECRET: self._api_secret,
                    }
                    if self._private_key:
                        data[CONF_PRIVATE_KEY] = self._private_key
                    if self._public_key:
                        data[CONF_PUBLIC_KEY] = self._public_key

                    return self.async_create_entry(
                        title=f"Threema {self._gateway_id}",
                        data=data,
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_GATEWAY_ID): str,
                vol.Required(CONF_API_SECRET): str,
                vol.Optional(CONF_PRIVATE_KEY, default=self._private_key or ""): str,
                vol.Optional(CONF_PUBLIC_KEY, default=self._public_key or ""): str,
            }
        )

        return self.async_show_form(
            step_id="credentials",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, _: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth if credentials become invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            api_secret = user_input[CONF_API_SECRET].strip()
            private_key_input = user_input.get(CONF_PRIVATE_KEY, "").strip() or None

            client = ThreemaAPIClient(
                self.hass,
                gateway_id=reauth_entry.data[CONF_GATEWAY_ID],
                api_secret=api_secret,
                private_key=private_key_input
                or reauth_entry.data.get(CONF_PRIVATE_KEY),
            )

            try:
                await client.validate_credentials()
            except ThreemaAuthError:
                errors["base"] = "invalid_auth"
            except ThreemaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating new credentials")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(reauth_entry.data[CONF_GATEWAY_ID])
                self._abort_if_unique_id_mismatch()
                data_updates: dict[str, str] = {
                    CONF_API_SECRET: api_secret,
                }
                if private_key_input:
                    data_updates[CONF_PRIVATE_KEY] = private_key_input
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=data_updates,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_SECRET): str,
                    vol.Optional(CONF_PRIVATE_KEY): str,
                }
            ),
            errors=errors,
        )


RECIPIENT_SCHEMA = vol.All(
    cv.string,
    cv.matches_regex(r"^[0-9A-Za-z]{8}$"),
    lambda value: value.upper(),
)


class RecipientSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a Threema recipient as a subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the recipient subentry step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                recipient_id = RECIPIENT_SCHEMA(user_input[CONF_RECIPIENT])
            except vol.Invalid:
                errors["base"] = "invalid_recipient_id"
            else:
                # Check for duplicate recipients
                for subentry in self._get_entry().subentries.values():
                    if subentry.data.get(CONF_RECIPIENT) == recipient_id:
                        return self.async_abort(reason="already_configured")

                raw_name = user_input.get("name", "").strip()
                name = f"{raw_name} ({recipient_id})" if raw_name else recipient_id

                return self.async_create_entry(
                    title=name,
                    data={CONF_RECIPIENT: recipient_id},
                    unique_id=recipient_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RECIPIENT): str,
                    vol.Optional("name"): str,
                }
            ),
            errors=errors,
        )
