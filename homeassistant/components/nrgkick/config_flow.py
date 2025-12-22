"""Config flow for NRGkick integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    NRGkickAPI,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
)
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import NRGkickConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    api = NRGkickAPI(
        host=data[CONF_HOST],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
        session=session,
    )

    await api.test_connection()

    info = await api.get_info(["general"])
    device_name = info.get("general", {}).get("device_name")
    if not device_name:
        device_name = "NRGkick"

    return {
        "title": device_name,
        "serial": info.get("general", {}).get("serial_number", "Unknown"),
    }


# pylint: disable=abstract-method  # is_matching is not required for HA config flows
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for NRGkick."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_host: str | None = None
        self._discovered_name: str | None = None

    # pylint: disable=unused-argument

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["serial"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "device_ip": user_input[CONF_HOST] if user_input else ""
            },
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        _LOGGER.debug("Discovered NRGkick device: %s", discovery_info)

        # Extract device information from mDNS metadata.
        serial = discovery_info.properties.get("serial_number")
        device_name = discovery_info.properties.get("device_name")
        model_type = discovery_info.properties.get("model_type")
        json_api_enabled = discovery_info.properties.get("json_api_enabled", "0")

        # Verify JSON API is enabled.
        if json_api_enabled != "1":
            _LOGGER.debug("NRGkick device %s does not have JSON API enabled", serial)
            return self.async_abort(reason="json_api_disabled")

        if not serial:
            _LOGGER.debug("NRGkick device discovered without serial number")
            return self.async_abort(reason="no_serial_number")

        # Set unique ID to prevent duplicate entries.
        await self.async_set_unique_id(serial)
        # Update the host if the device is already configured (IP might have changed).
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.host})

        # Store discovery info for the confirmation step.
        self._discovered_host = discovery_info.host
        # Fallback: device_name -> model_type -> "NRGkick".
        self._discovered_name = device_name or model_type or "NRGkick"
        self.context["title_placeholders"] = {"name": self._discovered_name}

        # Proceed to confirmation step.
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Build the connection data.
            data = {
                CONF_HOST: self._discovered_host,
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                info = await validate_input(self.hass, data)
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create entry directly - HA will show device/area assignment UI.
                # This is the final step, so "Skip and finish" is appropriate.
                return self.async_create_entry(title=info["title"], data=data)

        # Show confirmation form with optional authentication.
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "name": self._discovered_name or "NRGkick",
                "device_ip": self._discovered_host or "",
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return self.async_abort(reason="reauth_failed")

        entry = self.hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            return self.async_abort(reason="reauth_failed")

        if user_input is not None:
            data = {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                await validate_input(self.hass, data)
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reauthentication")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data=data, reason="reauth_successful"
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": entry.data[CONF_HOST],
                "device_ip": entry.data[CONF_HOST],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration confirmation."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if entry is None:
            return self.async_abort(reason="reconfigure_failed")

        if user_input is not None:
            data = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_USERNAME: user_input.get(CONF_USERNAME),
                CONF_PASSWORD: user_input.get(CONF_PASSWORD),
            }

            try:
                await validate_input(self.hass, data)
            except NRGkickApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except NRGkickApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data=data, reason="reconfigure_successful"
                )

        host = entry.data.get(CONF_HOST, "")
        username = entry.data.get(CONF_USERNAME) or ""
        password = entry.data.get(CONF_PASSWORD) or ""

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=host): str,
                    vol.Optional(CONF_USERNAME, default=username): str,
                    vol.Optional(CONF_PASSWORD, default=password): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": host,
                "device_ip": user_input[CONF_HOST] if user_input else host,
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: NRGkickConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for NRGkick."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        scan_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=scan_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
