"""Config flow for EnergyID integration.

Provides UI configuration flow for setting up webhook URL and entity mapping.
Validates connections and meter configurations against EnergyID API.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from energyid_webhooks import WebhookClientAsync
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENTITY_ID,
    CONF_METRIC,
    CONF_METRIC_KIND,
    CONF_UNIT,
    CONF_WEBHOOK_URL,
    DOMAIN,
    ENERGYID_METRIC_KINDS,
)

_LOGGER = logging.getLogger(__name__)


def hass_entity_ids(hass: HomeAssistant) -> list[str]:
    """Return all entity IDs in Home Assistant."""
    return list(hass.states.async_entity_ids())


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnergyID.

    Manages user configuration steps with error handling and input validation.
    Fetches available metrics and units from EnergyID meter catalog.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        # Get the meter catalog
        http_session = async_get_clientsession(self.hass)
        _client = WebhookClientAsync(webhook_url="", session=http_session)
        meter_catalog = await _client.get_meter_catalog()

        if user_input is not None:
            # Create a unique ID combining webhook URL and entity ID
            unique_id = f"{user_input[CONF_WEBHOOK_URL]}_{user_input[CONF_ENTITY_ID]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Validate input before attempting connection
            if any(
                entry.data[CONF_WEBHOOK_URL] == user_input[CONF_WEBHOOK_URL]
                and entry.data[CONF_ENTITY_ID] == user_input[CONF_ENTITY_ID]
                and entry.data[CONF_METRIC] == user_input[CONF_METRIC]
                and entry.data[CONF_METRIC_KIND] == user_input[CONF_METRIC_KIND]
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured_service")

            client = WebhookClientAsync(
                webhook_url=user_input[CONF_WEBHOOK_URL], session=http_session
            )
            try:
                await client.get_policy()
            except aiohttp.ClientResponseError:
                errors["base"] = "cannot_connect"
            except aiohttp.InvalidURL:
                errors[CONF_WEBHOOK_URL] = "invalid_url"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Send {user_input[CONF_ENTITY_ID]} to EnergyID",
                    data=user_input,
                )

        # Show the form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_WEBHOOK_URL): str,
                vol.Required(CONF_ENTITY_ID): vol.In(hass_entity_ids(self.hass)),
                vol.Required(CONF_METRIC): vol.In(sorted(meter_catalog.all_metrics)),
                vol.Required(CONF_METRIC_KIND): vol.In(ENERGYID_METRIC_KINDS),
                vol.Required(CONF_UNIT): vol.In(sorted(meter_catalog.all_units)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
