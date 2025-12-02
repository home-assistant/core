"""Config flow for Bbox integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiobbox import BboxApi, BboxApiError, BboxAuthError
from aiohttp import CookieJar
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_BASE, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_CONFIRM_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)

RECONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class BboxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bbox."""

    VERSION = 1
    MINOR_VERSION = 1

    reauth_entry: ConfigEntry | None = None
    reconfigure_entry: ConfigEntry | None = None

    async def _validate_connection(
        self, base_url: str, password: str, validate_unique_id: bool = True
    ) -> tuple[dict[str, str], str, str]:
        """Validate Bbox connection and return errors, unique_id, and title."""
        errors: dict[str, str] = {}

        if not base_url.startswith(("http://", "https://")):
            errors[CONF_BASE] = "invalid_base_url"
            return errors, "", ""

        if not base_url.endswith("/"):
            base_url += "/"

        try:
            # Create dedicated session with cookie support for Bbox authentication
            session = aiohttp_client.async_create_clientsession(
                self.hass,
                cookie_jar=CookieJar(unsafe=True),
            )

            client = BboxApi(
                password=password,
                base_url=base_url,
                timeout=10,
                session=session,
            )

            await client.authenticate()
            router_info = await client.get_router_info()

        except BboxAuthError:
            errors[CONF_BASE] = "invalid_auth"
        except BboxApiError as err:
            if "timeout" in str(err).lower():
                errors[CONF_BASE] = "timeout_connect"
            elif "connect" in str(err).lower():
                errors[CONF_BASE] = "cannot_connect"
            else:
                errors[CONF_BASE] = "unknown"
        except TimeoutError:
            errors[CONF_BASE] = "timeout_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors[CONF_BASE] = "unknown"
        finally:
            if "bbox" in locals():
                await client.close()

        if errors:
            return errors, "", ""

        unique_id = router_info.serialnumber
        title = f"Bbox {router_info.modelname}"

        if validate_unique_id:
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_BASE_URL: base_url})

        return errors, unique_id, title

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "base_url": DEFAULT_BASE_URL,
                },
            )

        base_url = user_input[CONF_BASE_URL]
        password = user_input[CONF_PASSWORD]

        errors, _, title = await self._validate_connection(base_url, password)
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "base_url": DEFAULT_BASE_URL,
                },
            )

        return self.async_create_entry(
            title=title,
            data=user_input,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None and self.reauth_entry is not None:
            password = user_input[CONF_PASSWORD]
            base_url = self.reauth_entry.data[CONF_BASE_URL]

            errors, unique_id, _ = await self._validate_connection(
                base_url, password, validate_unique_id=False
            )

            if not errors:
                # Verify we're updating the same device
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")

                # Update the entry with new password
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={**self.reauth_entry.data, CONF_PASSWORD: password},
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_CONFIRM_DATA_SCHEMA,
            description_placeholders={
                "base_url": self.reauth_entry.data[CONF_BASE_URL]
                if self.reauth_entry
                else "",
            },
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        self.reconfigure_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration confirmation."""
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure_confirm",
                data_schema=RECONFIGURE_DATA_SCHEMA,
                description_placeholders={
                    "base_url": self.reconfigure_entry.data[CONF_BASE_URL]
                    if self.reconfigure_entry
                    else "",
                },
            )

        base_url = user_input[CONF_BASE_URL]
        password = user_input[CONF_PASSWORD]

        errors, unique_id, _ = await self._validate_connection(
            base_url, password, validate_unique_id=False
        )

        if errors:
            return self.async_show_form(
                step_id="reconfigure_confirm",
                data_schema=RECONFIGURE_DATA_SCHEMA,
                errors=errors,
                description_placeholders={
                    "base_url": self.reconfigure_entry.data[CONF_BASE_URL]
                    if self.reconfigure_entry
                    else "",
                },
            )

        # Verify we're updating the same device
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_mismatch(reason="wrong_account")

        if self.reconfigure_entry is not None:
            # Update the entry with new configuration
            self.hass.config_entries.async_update_entry(
                self.reconfigure_entry,
                data={CONF_BASE_URL: base_url, CONF_PASSWORD: password},
            )
            await self.hass.config_entries.async_reload(self.reconfigure_entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_abort(reason="reconfigure_failed")
