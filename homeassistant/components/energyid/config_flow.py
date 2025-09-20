"""Config flow for EnergyID integration."""

import asyncio
from collections.abc import Mapping
import logging
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
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_PROVISIONING_KEY,
    CONF_PROVISIONING_SECRET,
    DOMAIN,
)
from .energyid_sensor_mapping_flow import EnergyIDSensorMappingFlowHandler

_LOGGER = logging.getLogger(__name__)

ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX = "homeassistant_eid_"

# Polling configuration
POLLING_INTERVAL = 2  # seconds
MAX_POLLING_ATTEMPTS = 60  # 2 minutes total


class EnergyIDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the EnergyID integration."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._flow_data: dict[str, Any] = {}
        self._polling_task: asyncio.Task | None = None

    async def _perform_auth_and_get_details(self) -> str | None:
        """Authenticate with EnergyID and retrieve device details."""
        _LOGGER.debug("Starting authentication with EnergyID")
        client = WebhookClient(
            provisioning_key=self._flow_data[CONF_PROVISIONING_KEY],
            provisioning_secret=self._flow_data[CONF_PROVISIONING_SECRET],
            device_id=self._flow_data[CONF_DEVICE_ID],
            device_name=self._flow_data[CONF_DEVICE_NAME],
            session=async_get_clientsession(self.hass),
        )
        try:
            is_claimed = await client.authenticate()
            _LOGGER.debug("Authentication successful, claimed: %s", is_claimed)
        except ClientError as err:
            _LOGGER.error(
                "Failed to connect to EnergyID during authentication: %s", err
            )
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error during EnergyID authentication")
            return "unknown_auth_error"

        if is_claimed:
            self._flow_data["record_number"] = client.recordNumber
            self._flow_data["record_name"] = client.recordName
            _LOGGER.debug(
                "Device claimed with record number: %s, record name: %s",
                client.recordNumber,
                client.recordName,
            )
            return None

        self._flow_data["claim_info"] = client.get_claim_info()
        _LOGGER.debug(
            "Device needs claim, claim info: %s", self._flow_data["claim_info"]
        )
        return "needs_claim"

    async def _async_poll_for_claim(self) -> None:
        """Poll EnergyID to check if device has been claimed."""
        for attempt in range(1, MAX_POLLING_ATTEMPTS + 1):
            await asyncio.sleep(POLLING_INTERVAL)

            _LOGGER.debug("Polling attempt %s for claim status", attempt)
            auth_status = await self._perform_auth_and_get_details()

            if auth_status is None:
                # Device has been claimed
                _LOGGER.debug("Device claimed detected during polling")
                # Trigger the flow to continue
                self.hass.async_create_task(
                    self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
                )
                return
            if auth_status != "needs_claim":
                # Some other error occurred
                _LOGGER.error("Error during polling: %s", auth_status)
                return

        _LOGGER.debug("Max polling attempts reached without successful claim")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        _LOGGER.debug("Starting user step with input: %s", user_input)
        errors: dict[str, str] = {}
        if user_input is not None:
            instance_id = await async_get_instance_id(self.hass)
            self._flow_data = {
                **user_input,
                CONF_DEVICE_ID: f"{ENERGYID_DEVICE_ID_FOR_WEBHOOK_PREFIX}{instance_id}",
                CONF_DEVICE_NAME: self.hass.config.location_name,
            }
            _LOGGER.debug("Flow data after user input: %s", self._flow_data)

            auth_status = await self._perform_auth_and_get_details()

            if auth_status is None:
                await self.async_set_unique_id(self._flow_data["record_number"])
                self._abort_if_unique_id_configured()
                _LOGGER.debug(
                    "Creating entry with title: %s", self._flow_data["record_name"]
                )
                return self.async_create_entry(
                    title=self._flow_data["record_name"], data=self._flow_data
                )

            if auth_status == "needs_claim":
                _LOGGER.debug("Redirecting to auth and claim step")
                return await self.async_step_auth_and_claim()

            errors["base"] = auth_status
            _LOGGER.debug("Errors encountered during user step: %s", errors)

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
                "docs_url": "https://app.energyid.eu/integrations/home-assistant"
            },
        )

    async def async_step_auth_and_claim(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the step for device claiming using external step with polling."""
        _LOGGER.debug("Starting auth and claim step with input: %s", user_input)

        claim_info = self._flow_data.get("claim_info", {})

        # Start polling when we first enter this step
        if self._polling_task is None:
            self._polling_task = self.hass.async_create_task(
                self._async_poll_for_claim()
            )

            # Show external step to open the EnergyID website
            return self.async_external_step(
                step_id="auth_and_claim",
                url=claim_info.get("claim_url", ""),
                description_placeholders=claim_info,
            )

        # Check if device has been claimed
        auth_status = await self._perform_auth_and_get_details()

        if auth_status is None:
            # Device has been claimed
            await self.async_set_unique_id(self._flow_data["record_number"])
            self._abort_if_unique_id_configured()
            return self.async_external_step_done(next_step_id="create_entry")

        # Device not claimed yet, show the external step again
        return self.async_external_step(
            step_id="auth_and_claim",
            url=claim_info.get("claim_url", ""),
            description_placeholders=claim_info,
        )

    async def async_step_create_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Final step to create the entry after successful claim."""
        _LOGGER.debug("Creating entry with title: %s", self._flow_data["record_name"])
        return self.async_create_entry(
            title=self._flow_data["record_name"], data=self._flow_data
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication upon an API authentication error."""
        self._flow_data = {
            CONF_DEVICE_ID: entry_data[CONF_DEVICE_ID],
            CONF_DEVICE_NAME: entry_data[CONF_DEVICE_NAME],
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._flow_data.update(user_input)
            auth_status = await self._perform_auth_and_get_details()

            if auth_status is None:
                # Authentication successful and claimed
                await self.async_set_unique_id(self._flow_data["record_number"])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_PROVISIONING_KEY: user_input[CONF_PROVISIONING_KEY],
                        CONF_PROVISIONING_SECRET: user_input[CONF_PROVISIONING_SECRET],
                    },
                )

            if auth_status == "needs_claim":
                return await self.async_step_auth_and_claim()

            errors["base"] = auth_status

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVISIONING_KEY): str,
                    vol.Required(CONF_PROVISIONING_SECRET): cv.string,
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://app.energyid.eu/integrations/home-assistant"
            },
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"sensor_mapping": EnergyIDSensorMappingFlowHandler}
