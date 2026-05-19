"""Config flow for ESPHome Dashboard integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
from esphome_dashboard_api import ESPHomeDashboardAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


class ESPHomeDashboardConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESPHome Dashboard."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _validate_input(
        self, url: str, username: str | None, password: str | None
    ) -> dict[str, str]:
        """Validate the user input and test connection.

        Returns a dict of errors, empty if validation succeeds.
        """
        errors: dict[str, str] = {}

        # Validate URL format
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors["base"] = "invalid_url"
                return errors
            # Access port to validate it's in valid range (0-65535)
            # This raises ValueError if port is out of range
            _ = parsed.port
        except ValueError:
            errors["base"] = "invalid_url"
            return errors

        # Test connection to the dashboard
        auth = aiohttp.BasicAuth(username, password) if username and password else None
        session = aiohttp_client.async_create_clientsession(
            self.hass, auth=auth, raise_for_status=True
        )

        try:
            api = ESPHomeDashboardAPI(url, session)
            await api.request("GET", "login")
            devices_data = await api.get_devices()
            if "configured" not in devices_data:
                errors["base"] = "invalid_dashboard"
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                errors["base"] = "invalid_auth"
            else:
                _LOGGER.exception("Failed to connect to ESPHome Dashboard")
                errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Failed to connect to ESPHome Dashboard")
            errors["base"] = "cannot_connect"
        finally:
            await session.close()

        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            # Validate input
            errors = await self._validate_input(url, username, password)

            if not errors:
                # Create a unique ID based on the URL
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()

                # Prepare entry data
                data = {CONF_URL: url}
                if username:
                    data[CONF_USERNAME] = username
                    data[CONF_PASSWORD] = password

                parsed = urlparse(url)
                return self.async_create_entry(
                    title=f"ESPHome Dashboard ({parsed.netloc})",
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "local_url": "http://192.168.1.100:6052",
                "remote_url": "http://esphome.example.com",
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the dashboard URL."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            # Validate input
            errors = await self._validate_input(url, username, password)

            if not errors:
                # Check if the new URL is already configured by another entry
                reconfigure_entry = self._get_reconfigure_entry()
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured(
                    updates={CONF_URL: url},
                    reload_on_update=False,
                )

                # Update the unique ID and URL
                self.hass.config_entries.async_update_entry(
                    reconfigure_entry, unique_id=url
                )

                # Prepare data updates
                data_updates = {CONF_URL: url}
                if username:
                    data_updates[CONF_USERNAME] = username
                    data_updates[CONF_PASSWORD] = password
                else:
                    # Remove auth if not provided
                    data_updates[CONF_USERNAME] = None
                    data_updates[CONF_PASSWORD] = None

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates=data_updates,
                )

        # Get current URL and credentials for reconfiguration form
        reconfigure_entry = self._get_reconfigure_entry()
        suggested_values: dict[str, Any] = {
            CONF_URL: reconfigure_entry.data[CONF_URL],
        }
        if CONF_USERNAME in reconfigure_entry.data:
            suggested_values[CONF_USERNAME] = reconfigure_entry.data[CONF_USERNAME]
            suggested_values[CONF_PASSWORD] = reconfigure_entry.data.get(
                CONF_PASSWORD, ""
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested_values
            ),
            errors=errors,
            description_placeholders={
                "local_url": "http://192.168.1.100:6052",
                "remote_url": "http://esphome.example.com",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth flow when credentials expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            # Validate input
            url = reauth_entry.data[CONF_URL]
            errors = await self._validate_input(url, username, password)

            if not errors:
                # Update credentials
                data_updates = {}
                if username:
                    data_updates[CONF_USERNAME] = username
                    data_updates[CONF_PASSWORD] = password
                else:
                    data_updates[CONF_USERNAME] = None
                    data_updates[CONF_PASSWORD] = None

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=data_updates,
                )

        # Show reauth form - don't pre-fill password for security
        suggested_values: dict[str, Any] = {}
        if CONF_USERNAME in reauth_entry.data:
            suggested_values[CONF_USERNAME] = reauth_entry.data[CONF_USERNAME]

        reauth_schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                reauth_schema, suggested_values
            ),
            errors=errors,
            description_placeholders={"url": reauth_entry.data[CONF_URL]},
        )
