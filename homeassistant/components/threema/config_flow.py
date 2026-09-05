"""Config flow for Threema Gateway integration."""

from collections.abc import Mapping
import logging
import re
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME, CONF_RECIPIENT
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import (
    ThreemaAPIClient,
    ThreemaAuthError,
    ThreemaConnectionError,
    derive_public_key,
    generate_key_pair,
)
from .const import (
    CONF_API_SECRET,
    CONF_GATEWAY_ID,
    CONF_PRIVATE_KEY,
    DOMAIN,
    SUBENTRY_TYPE_RECIPIENT,
)

_LOGGER = logging.getLogger(__name__)

_KEY_HEX_LENGTH = 64
_KEY_PREFIXES = ("private:", "public:")
_CONF_PUBLIC_KEY = "public_key"
_GATEWAY_ID_REGEX = re.compile(r"^\*[A-Z0-9]{7}$")


def _strip_key_prefix(value: str, expected_prefix: str) -> str | None:
    """Strip the expected Threema key-export prefix, if present.

    Returns None if the value carries a *different* key-type prefix (e.g.
    a 'public:' key pasted into the private-key field), so the mismatch
    can be rejected instead of silently accepted as the wrong key type.
    """
    lowered = value.lower()
    for prefix in _KEY_PREFIXES:
        if lowered.startswith(prefix):
            if prefix != expected_prefix:
                return None
            return value[len(prefix) :].strip()
    return value


def _is_valid_key_hex(value: str) -> bool:
    """Return True if value is a 64-character hex string (32-byte NaCl key)."""
    if len(value) != _KEY_HEX_LENGTH:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


class ThreemaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Threema Gateway."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {SUBENTRY_TYPE_RECIPIENT: RecipientSubentryFlowHandler}

    _gateway_id: str | None = None
    _api_secret: str | None = None
    _private_key: str | None = None
    _public_key: str | None = None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - choose setup type."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["credentials", "setup_new"],
        )

    async def async_step_setup_new(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Generate keys for a new Gateway ID."""
        if user_input is not None:
            return await self.async_step_credentials()

        try:
            private_key, public_key = await self.hass.async_add_executor_job(
                generate_key_pair
            )
        except Exception:
            _LOGGER.exception("Failed to generate key pair")
            return self.async_abort(reason="key_generation_failed")

        self._private_key = private_key

        return self.async_show_form(
            step_id="setup_new",
            description_placeholders={
                "public_key": public_key,
                "private_key": private_key,
            },
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect Gateway credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            gateway_id = user_input[CONF_GATEWAY_ID].strip().upper()

            if not _GATEWAY_ID_REGEX.match(gateway_id):
                errors["base"] = "invalid_gateway_id"
            else:
                await self.async_set_unique_id(gateway_id)
                self._abort_if_unique_id_configured()

                self._gateway_id = gateway_id
                self._api_secret = user_input[CONF_API_SECRET].strip()

                raw_private_key = user_input.get(CONF_PRIVATE_KEY, "").strip()
                self._private_key = raw_private_key or None
                raw_public_key = user_input.get(_CONF_PUBLIC_KEY, "").strip()
                self._public_key = raw_public_key or None

                private_key = (
                    _strip_key_prefix(raw_private_key, "private:")
                    if raw_private_key
                    else None
                )
                public_key = (
                    _strip_key_prefix(raw_public_key, "public:")
                    if raw_public_key
                    else None
                )

                if raw_private_key and private_key is None:
                    errors[CONF_PRIVATE_KEY] = "invalid_key"
                elif raw_public_key and public_key is None:
                    errors[_CONF_PUBLIC_KEY] = "invalid_key"
                elif private_key and not _is_valid_key_hex(private_key):
                    errors[CONF_PRIVATE_KEY] = "invalid_key"
                elif public_key and not _is_valid_key_hex(public_key):
                    errors[_CONF_PUBLIC_KEY] = "invalid_key"
                elif public_key and not private_key:
                    errors[_CONF_PUBLIC_KEY] = "public_key_requires_private_key"
                elif (
                    private_key
                    and public_key
                    and derive_public_key(private_key).lower() != public_key.lower()
                ):
                    errors[_CONF_PUBLIC_KEY] = "key_mismatch"
                else:
                    client = ThreemaAPIClient(
                        self.hass,
                        gateway_id=gateway_id,
                        api_secret=self._api_secret,
                        private_key=private_key,
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
                        if private_key:
                            data[CONF_PRIVATE_KEY] = private_key

                        return self.async_create_entry(
                            title=f"Threema {self._gateway_id}",
                            data=data,
                        )

        schema = vol.Schema(
            {
                vol.Required(CONF_GATEWAY_ID, default=self._gateway_id or ""): str,
                vol.Required(
                    CONF_API_SECRET, default=self._api_secret or ""
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Optional(
                    CONF_PRIVATE_KEY, default=self._private_key or ""
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                vol.Optional(
                    _CONF_PUBLIC_KEY, default=self._public_key or ""
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            }
        )

        return self.async_show_form(
            step_id="credentials",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth flow triggered by an expired or invalid API secret."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new API secret during reauthentication."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            new_api_secret = user_input[CONF_API_SECRET].strip()
            client = ThreemaAPIClient(
                self.hass,
                gateway_id=reauth_entry.data[CONF_GATEWAY_ID],
                api_secret=new_api_secret,
                private_key=reauth_entry.data.get(CONF_PRIVATE_KEY),
            )
            try:
                await client.validate_credentials()
            except ThreemaAuthError:
                errors["base"] = "invalid_auth"
            except ThreemaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_SECRET: new_api_secret},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_SECRET): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "gateway_id": reauth_entry.data[CONF_GATEWAY_ID],
            },
        )


_RECIPIENT_ID_REGEX = re.compile(r"^[0-9A-Za-z]{8}$")


class RecipientSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a Threema recipient as a subentry."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Handle the recipient subentry step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            recipient_id = user_input[CONF_RECIPIENT].strip().upper()

            if not _RECIPIENT_ID_REGEX.match(recipient_id):
                errors[CONF_RECIPIENT] = "invalid_recipient_id"
            else:
                # Check for duplicate recipients
                for subentry in self._get_entry().subentries.values():
                    if subentry.data.get(CONF_RECIPIENT) == recipient_id:
                        return self.async_abort(reason="already_configured")

                raw_name = user_input.get(CONF_NAME, "").strip()
                title = f"{raw_name} ({recipient_id})" if raw_name else recipient_id

                data: dict[str, str] = {CONF_RECIPIENT: recipient_id}
                if raw_name:
                    data[CONF_NAME] = raw_name

                return self.async_create_entry(
                    title=title,
                    data=data,
                    unique_id=recipient_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_RECIPIENT): str,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )
