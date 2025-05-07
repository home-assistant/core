"""Config flow for EnergyID integration."""

import logging
import secrets
from typing import Any

from aiohttp import ClientError
from energyid_webhooks.client_v2 import WebhookClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from . import EnergyIDConfigEntry
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from .subentry_flow import EnergyIDSubentryFlowHandler

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENERGYID_DEVICE_NAME_FOR_WEBHOOK = "Home Assistant"
ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX = "homeassistant_eid_"


def _generate_energyid_device_id_for_webhook() -> str:
    """Generate a unique device ID for this Home Assistant instance to use with EnergyID webhook."""
    return f"{ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX}{secrets.token_hex(4)}"


class EnergyIDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the EnergyID integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow with default flow data."""
        self._flow_data: dict[str, Any] = {
            "provisioning_key": None,
            "provisioning_secret": None,
            "webhook_device_id": _generate_energyid_device_id_for_webhook(),
            "webhook_device_name": DEFAULT_ENERGYID_DEVICE_NAME_FOR_WEBHOOK,
            "claim_info": None,
            "record_number": None,
            "record_name": None,
        }

    async def _perform_auth_and_get_details(self) -> str | None:
        """Authenticate with EnergyID and retrieve device details."""
        if (
            not self._flow_data["provisioning_key"]
            or not self._flow_data["provisioning_secret"]
        ):
            _LOGGER.error("Missing credentials for authentication")
            return "missing_credentials"

        _LOGGER.debug(
            "Attempting authentication with device ID: %s, device name: %s",
            self._flow_data["webhook_device_id"],
            self._flow_data["webhook_device_name"],
        )

        session = async_get_clientsession(self.hass)
        client = WebhookClient(
            provisioning_key=self._flow_data["provisioning_key"],
            provisioning_secret=self._flow_data["provisioning_secret"],
            device_id=self._flow_data["webhook_device_id"],
            device_name=self._flow_data["webhook_device_name"],
            session=session,
        )

        try:
            session = async_get_clientsession(self.hass)
            client = WebhookClient(
                provisioning_key=self._flow_data["provisioning_key"],
                provisioning_secret=self._flow_data["provisioning_secret"],
                device_id=self._flow_data["webhook_device_id"],
                device_name=self._flow_data["webhook_device_name"],
                session=session,
            )
        except ClientError:
            _LOGGER.warning(
                "Connection error during EnergyID authentication", exc_info=True
            )
            return "cannot_connect"
        except RuntimeError:
            _LOGGER.exception("Unexpected runtime error during EnergyID authentication")
            return "unknown_auth_error"

        # Now we're outside the try-except block, with a successfully created client
        try:
            is_claimed = await client.authenticate()
        except ClientError:
            _LOGGER.warning(
                "Connection error during EnergyID authentication", exc_info=True
            )
            return "cannot_connect"
        except RuntimeError:
            _LOGGER.exception("Unexpected runtime error during EnergyID authentication")
            return "unknown_auth_error"

        # If we get here, the client was authenticated successfully
        if is_claimed:
            self._flow_data["record_number"] = client.recordNumber
            self._flow_data["record_name"] = client.recordName
            self._flow_data["claim_info"] = None
            _LOGGER.info(
                "Successfully authenticated and claimed. Record: %s, Name: %s",
                client.recordNumber,
                client.recordName,
            )
            if not self._flow_data["record_number"]:
                _LOGGER.error("Claimed, but no record number received from EnergyID")
                return "missing_record_number"
            return None  # Successfully claimed

        # Device not claimed - we only reach here if is_claimed was False
        claim_details_dict = client.get_claim_info()
        self._flow_data["claim_info"] = claim_details_dict
        _LOGGER.info("Device needs to be claimed. Claim info: %s", claim_details_dict)
        if not claim_details_dict or not claim_details_dict.get("claim_code"):
            _LOGGER.error(
                "Failed to retrieve valid claim code. Info: %s", claim_details_dict
            )
            return "cannot_retrieve_claim_info"
        return "needs_claim"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        errors: dict[str, str] = {}
        _LOGGER.debug("User step input: %s", user_input)

        if user_input is not None:
            self._flow_data["provisioning_key"] = user_input[CONF_PROVISIONING_KEY]
            self._flow_data["provisioning_secret"] = user_input[
                CONF_PROVISIONING_SECRET
            ]
            auth_status = await self._perform_auth_and_get_details()
            _LOGGER.debug("Authentication status: %s", auth_status)

            if auth_status is None:
                await self.async_set_unique_id(str(self._flow_data["record_number"]))
                self._abort_if_unique_id_configured()
                return await self.async_step_finalize()
            if auth_status == "needs_claim":
                if not self._flow_data.get("claim_info"):
                    _LOGGER.error("Claim info is missing despite 'needs_claim' status")
                    return self.async_abort(reason="internal_error_no_claim_info")
                return await self.async_step_auth_and_claim()
            errors["base"] = auth_status

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVISIONING_KEY): str,
                    vol.Required(CONF_PROVISIONING_SECRET): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://help.energyid.eu/en/developer/incoming-webhooks/"
            },
        )

    async def async_step_auth_and_claim(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step for device claiming if needed."""
        errors: dict[str, str] = {}
        _LOGGER.debug(
            "Auth and claim step input: %s, claim info: %s",
            user_input,
            self._flow_data.get("claim_info"),
        )

        if user_input is not None:
            auth_status = await self._perform_auth_and_get_details()
            _LOGGER.debug("Authentication status after claim attempt: %s", auth_status)
            if auth_status is None:
                if not self._flow_data.get("record_number"):
                    _LOGGER.error("Claim successful but record number is missing")
                    errors["base"] = "missing_record_number"
                else:
                    await self.async_set_unique_id(
                        str(self._flow_data["record_number"])
                    )
                    self._abort_if_unique_id_configured()
                    return await self.async_step_finalize()
            elif auth_status == "needs_claim":
                errors["base"] = "claim_failed_or_timed_out"
            else:
                errors["base"] = auth_status

        placeholders_for_form = {
            "claim_url": "N/A",
            "claim_code": "N/A",
            "valid_until": "N/A",
        }
        current_claim_info = self._flow_data.get("claim_info")

        if isinstance(current_claim_info, dict):
            placeholders_for_form.update(
                {
                    "claim_url": current_claim_info.get("claim_url", "N/A"),
                    "claim_code": current_claim_info.get("claim_code", "N/A"),
                    "valid_until": current_claim_info.get("valid_until", "N/A"),
                }
            )
        else:
            _LOGGER.warning("Claim info is invalid or missing: %s", current_claim_info)
            if user_input is None and not errors.get("base"):
                errors["base"] = "cannot_retrieve_claim_info"

        return self.async_show_form(
            step_id="auth_and_claim",
            description_placeholders=placeholders_for_form,
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_finalize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finalize the configuration flow and create the config entry."""
        errors: dict[str, str] = {}
        _LOGGER.debug("Finalize step input: %s", user_input)

        required_keys = [
            "provisioning_key",
            "provisioning_secret",
            "webhook_device_id",
            "record_number",
        ]
        if not all(self._flow_data.get(k) for k in required_keys):
            _LOGGER.error("Incomplete flow data: %s", self._flow_data)
            return self.async_abort(reason="internal_flow_data_missing")

        if user_input is not None:
            self._flow_data["webhook_device_name"] = user_input[CONF_DEVICE_NAME]
            config_data_to_store = {
                CONF_PROVISIONING_KEY: self._flow_data["provisioning_key"],
                CONF_PROVISIONING_SECRET: self._flow_data["provisioning_secret"],
                CONF_DEVICE_ID: self._flow_data["webhook_device_id"],
                CONF_DEVICE_NAME: self._flow_data["webhook_device_name"],
            }
            ha_entry_title = (
                self._flow_data.get("record_name")
                or self._flow_data["webhook_device_name"]
            )
            return self.async_create_entry(
                title=ha_entry_title, data=config_data_to_store
            )

        suggested_name = (
            self._flow_data.get("record_name")
            if self._flow_data.get("record_name")
            and str(self._flow_data.get("record_name", "")).lower() != "none"
            else self._flow_data["webhook_device_name"]
        )
        ha_title_value = self._flow_data.get("record_name") or "your EnergyID site"
        placeholders_for_finalize = {"ha_entry_title_to_be": str(ha_title_value)}

        return self.async_show_form(
            step_id="finalize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_NAME, default=suggested_name): str,
                }
            ),
            description_placeholders=placeholders_for_finalize,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: EnergyIDConfigEntry,
    ) -> EnergyIDSubentryFlowHandler:
        """Return the options flow handler for the EnergyID integration."""
        return EnergyIDSubentryFlowHandler()
