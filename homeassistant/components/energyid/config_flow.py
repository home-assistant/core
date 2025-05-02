"""Config flow for EnergyID integration."""

import logging
from typing import Any

from aiohttp import ClientError
from energyid_webhooks.client_v2 import WebhookClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from .subentry_flow import EnergyIDSubentryFlowHandler

_LOGGER = logging.getLogger(__name__)


class EnergyIDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the main config flow for EnergyID."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._credentials: dict[str, Any] = {}
        self._claim_info: dict[str, Any] | None = None
        self._reauth_entry: ConfigEntry | None = None

    async def _test_connection(self) -> tuple[bool, dict[str, Any] | None]:
        """Test connection and get claim status using provided credentials."""
        session = async_get_clientsession(self.hass)
        client = WebhookClient(
            provisioning_key=self._credentials[CONF_PROVISIONING_KEY],
            provisioning_secret=self._credentials[CONF_PROVISIONING_SECRET],
            device_id=self._credentials[CONF_DEVICE_ID],
            device_name=self._credentials[CONF_DEVICE_NAME],
            session=session,
        )
        try:
            is_claimed = await client.authenticate()
            claim_info = None if is_claimed else client.get_claim_info()
        except ClientError as err:
            _LOGGER.error("Communication error during authentication: %s", err)
            raise ConnectionError from err
        except RuntimeError as err:
            _LOGGER.exception("Unexpected runtime error during authentication")
            raise ConnectionError from err
        else:
            if client.session.closed:
                await client.close()
            return is_claimed, claim_info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            self._credentials = user_input
            try:
                is_claimed, claim_info = await self._test_connection()
                if is_claimed:
                    return self.async_create_entry(
                        title=user_input[CONF_DEVICE_NAME], data=user_input
                    )
                self._claim_info = claim_info
                return await self.async_step_claim()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except RuntimeError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVISIONING_KEY): str,
                    vol.Required(CONF_PROVISIONING_SECRET): str,
                    vol.Required(CONF_DEVICE_ID): str,
                    vol.Required(CONF_DEVICE_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_claim(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the device claiming step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                is_claimed, claim_info = await self._test_connection()
                if is_claimed:
                    return self.async_create_entry(
                        title=self._credentials[CONF_DEVICE_NAME],
                        data=self._credentials,
                    )
                self._claim_info = claim_info
                errors["base"] = "claim_failed"
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except RuntimeError:
                errors["base"] = "unknown"

        if not self._claim_info:
            return self.async_abort(reason="unknown")

        return self.async_show_form(
            step_id="claim",
            description_placeholders={
                "claim_url": self._claim_info["claim_url"],
                "claim_code": self._claim_info["claim_code"],
                "valid_until": self._claim_info["valid_until"],
            },
            data_schema=vol.Schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> EnergyIDSubentryFlowHandler:
        """Get the options flow for this handler."""
        return EnergyIDSubentryFlowHandler()
