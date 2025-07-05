"""Config flow for EnergyID integration."""

from collections.abc import Callable
import logging
import secrets
from typing import Any

from aiohttp import ClientError
from energyid_webhooks.client_v2 import WebhookClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from .energyid_sensor_mapping_flow import EnergyIDSensorMappingFlowHandler

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENERGYID_DEVICE_NAME_FOR_WEBHOOK = "Home Assistant"
ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX = "homeassistant_eid_"


class EnergyIDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the EnergyID integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow with default flow data."""
        self._flow_data: dict[str, Any] = {
            "provisioning_key": None,
            "provisioning_secret": None,
            "webhook_device_id": None,
            "webhook_device_name": DEFAULT_ENERGYID_DEVICE_NAME_FOR_WEBHOOK,
            "claim_info": None,
            "record_number": None,
            "record_name": None,
        }

    async def _perform_auth_and_get_details(self) -> str | None:
        """Authenticate with EnergyID and retrieve device details."""
        _LOGGER.debug(
            "Attempting auth with device ID: %s, name: %s",
            self._flow_data["webhook_device_id"],
            self._flow_data["webhook_device_name"],
        )
        client = WebhookClient(
            provisioning_key=self._flow_data["provisioning_key"],
            provisioning_secret=self._flow_data["provisioning_secret"],
            device_id=self._flow_data["webhook_device_id"],
            device_name=self._flow_data["webhook_device_name"],
            session=async_get_clientsession(self.hass),
        )
        try:
            is_claimed = await client.authenticate()
        except ClientError:
            return "cannot_connect"
        except RuntimeError:
            _LOGGER.exception("Unexpected runtime error during EnergyID authentication")
            return "unknown_auth_error"

        if is_claimed:
            self._flow_data["record_number"] = client.recordNumber
            self._flow_data["record_name"] = client.recordName
            self._flow_data["claim_info"] = None
            _LOGGER.debug(
                "Successfully authenticated. Record: %s, Name: %s",
                client.recordNumber,
                client.recordName,
            )
            if not self._flow_data["record_number"]:
                return "missing_record_number"
            return None

        claim_details_dict = client.get_claim_info()
        self._flow_data["claim_info"] = claim_details_dict
        _LOGGER.debug("Device needs to be claimed. Info: %s", claim_details_dict)
        if not claim_details_dict or not claim_details_dict.get("claim_code"):
            return "cannot_retrieve_claim_info"
        return "needs_claim"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        if self._flow_data.get("webhook_device_id") is None:
            if (
                hasattr(self.hass.config, "instance_id")
                and self.hass.config.instance_id
            ):
                self._flow_data["webhook_device_id"] = (
                    f"{ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX}{self.hass.config.instance_id}"
                )
            else:
                _LOGGER.warning("HA instance_id not found, using random token")
                self._flow_data["webhook_device_id"] = (
                    f"{ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX}{secrets.token_hex(8)}"
                )

        errors: dict[str, str] = {}
        if user_input is not None:
            self._flow_data.update(user_input)
            auth_status = await self._perform_auth_and_get_details()
            if auth_status is None:
                record_num_str = str(self._flow_data["record_number"])
                await self.async_set_unique_id(record_num_str)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_PROVISIONING_KEY: self._flow_data["provisioning_key"],
                        CONF_PROVISIONING_SECRET: self._flow_data[
                            "provisioning_secret"
                        ],
                    }
                )
                return await self.async_step_finalize()
            if auth_status == "needs_claim":
                if not self._flow_data.get("claim_info"):
                    _LOGGER.error("Claim info missing despite 'needs_claim' status")
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
        if user_input is not None:
            auth_status = await self._perform_auth_and_get_details()
            if auth_status is None:
                if not self._flow_data.get("record_number"):
                    errors["base"] = "missing_record_number"
                else:
                    record_num_str = str(self._flow_data["record_number"])
                    await self.async_set_unique_id(record_num_str)
                    self._abort_if_unique_id_configured()
                    return await self.async_step_finalize()
            elif auth_status == "needs_claim":
                errors["base"] = "claim_failed_or_timed_out"
            else:
                errors["base"] = auth_status

        placeholders = {"claim_url": "N/A", "claim_code": "N/A", "valid_until": "N/A"}
        if isinstance(current_claim_info := self._flow_data.get("claim_info"), dict):
            placeholders["claim_url"] = current_claim_info.get("claim_url", "N/A")
            placeholders["claim_code"] = current_claim_info.get("claim_code", "N/A")
            placeholders["valid_until"] = current_claim_info.get("valid_until", "N/A")
        elif not errors.get("base"):
            _LOGGER.warning("Claim info invalid/missing: %s", current_claim_info)
            errors["base"] = "cannot_retrieve_claim_info"

        return self.async_show_form(
            step_id="auth_and_claim",
            description_placeholders=placeholders,
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_finalize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finalize the configuration flow and create the config entry."""
        required = [
            "provisioning_key",
            "provisioning_secret",
            "webhook_device_id",
            "record_number",
        ]
        if not all(self._flow_data.get(k) for k in required):
            _LOGGER.error("Incomplete flow data for finalize: %s", self._flow_data)
            return self.async_abort(reason="internal_flow_data_missing")

        if user_input is not None:
            self._flow_data["webhook_device_name"] = user_input[CONF_DEVICE_NAME]
            data = {
                CONF_PROVISIONING_KEY: self._flow_data["provisioning_key"],
                CONF_PROVISIONING_SECRET: self._flow_data["provisioning_secret"],
                CONF_DEVICE_ID: self._flow_data["webhook_device_id"],
                CONF_DEVICE_NAME: self._flow_data["webhook_device_name"],
            }
            title = (
                self._flow_data.get("record_name")
                or self._flow_data["webhook_device_name"]
            )
            return self.async_create_entry(title=str(title), data=data, options={})

        suggested_name = self._flow_data.get("record_name") or self._flow_data.get(
            "webhook_device_name"
        )
        placeholders = {
            "ha_entry_title_to_be": str(
                self._flow_data.get("record_name") or "your EnergyID site"
            )
        }

        return self.async_show_form(
            step_id="finalize",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_NAME, default=str(suggested_name)): str}
            ),
            description_placeholders=placeholders,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(  # type: ignore[override]
        cls, config_entry: ConfigEntry
    ) -> dict[str, Callable[[], ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {
            "sensor_mapping": lambda: EnergyIDSensorMappingFlowHandler(config_entry)
        }
