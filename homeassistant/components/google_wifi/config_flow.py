"""Config flow for Google Wifi Integration."""

import ipaddress
import logging

import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    try:
        # Check if the provided string is a valid IP address
        ipaddress.ip_address(data[CONF_IP_ADDRESS])
    except ValueError:
        raise InvalidIPAddress from None

    # Validate Connectivity (New)
    def fetch_status():
        url = f"http://{data[CONF_IP_ADDRESS]}/api/v1/status"
        return requests.get(url, timeout=5)

    try:
        response = await hass.async_add_executor_job(fetch_status)
        response.raise_for_status()
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as err:
        raise CannotConnect from err

    # Return info that you want to store in the config entry
    return {"title": data[CONF_IP_ADDRESS]}


class GoogleWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Wifi Integration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle the initial step where the user enters the IP."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)

                # If validation passes, create the config entry
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            except InvalidIPAddress:
                errors["base"] = "invalid_ip"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Show the form to the user (either initially or with errors)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, "Google Wifi")
                        if user_input
                        else "Google Wifi",
                    ): str,
                    vol.Required(
                        CONF_IP_ADDRESS,
                        default=user_input.get(CONF_IP_ADDRESS, "")
                        if user_input
                        else "",
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, user_input: dict) -> ConfigFlowResult:
        """Handle import of configuration from YAML."""
        # Check if the IP address is already in an existing ConfigEntry
        self._async_abort_entries_match({CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS]})

        # Ensure a name is set for imported configurations
        if CONF_NAME not in user_input:
            user_input = {**user_input, CONF_NAME: "Google Wifi"}
        try:
            await validate_input(self.hass, user_input)
        except InvalidIPAddress:
            # Abort import if the YAML configuration contains an invalid IP
            return self.async_abort(reason="invalid_ip")
        except CannotConnect:
            # Abort import if the configured device cannot be reached
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception during import")
            return self.async_abort(reason="unknown")
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
        )

    async def async_step_reconfigure(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **user_input}
                )
            except InvalidIPAddress:
                errors["base"] = "invalid_ip"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, entry.data.get(CONF_NAME))
                        if user_input
                        else entry.data.get(CONF_NAME),
                    ): str,
                    vol.Required(
                        CONF_IP_ADDRESS,
                        default=user_input.get(
                            CONF_IP_ADDRESS, entry.data.get(CONF_IP_ADDRESS)
                        )
                        if user_input
                        else entry.data.get(CONF_IP_ADDRESS),
                    ): str,
                }
            ),
            errors=errors,
        )


class InvalidIPAddress(Exception):
    """Error to indicate the IP address format is invalid."""


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""
