"""Config flow for EnergyID integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from energyid_webhooks import WebhookClientAsync
from energyid_webhooks.webhookpolicy import WebhookPolicy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_DATA_INTERVAL,
    CONF_ENTITY_ID,
    CONF_METRIC,
    CONF_METRIC_KIND,
    CONF_UNIT,
    CONF_UPLOAD_INTERVAL,
    CONF_WEBHOOK_URL,
    DEFAULT_DATA_INTERVAL,
    DEFAULT_UPLOAD_INTERVAL,
    DOMAIN,
    ENERGYID_INTERVALS,
    ENERGYID_METRIC_KINDS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_interval(interval: str, webhook_policy: WebhookPolicy) -> bool:
    """Validate if the interval is valid for the webhook policy."""
    if interval not in webhook_policy.allowed_intervals:
        raise InvalidInterval
    return True


def hass_entity_ids(hass: HomeAssistant) -> list[str]:
    """Return all entity IDs in Home Assistant."""
    return list(hass.states.async_entity_ids())


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for EnergyID."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        # Get the meter catalog
        http_session = async_get_clientsession(self.hass)
        # Temporary client without webhook URL (not yet known, but not needed for catalog)
        _client = WebhookClientAsync(webhook_url=None, session=http_session)
        meter_catalog = await _client.get_meter_catalog()

        # Handle the user input
        if user_input is not None:
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow changes."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            http_session = async_get_clientsession(self.hass)
            client = WebhookClientAsync(
                webhook_url=self.config_entry.data.get(CONF_WEBHOOK_URL),
                session=http_session,
            )
            try:
                webhook_policy = await client.policy
                await validate_interval(
                    interval=user_input[CONF_DATA_INTERVAL],
                    webhook_policy=webhook_policy,
                )
            except InvalidInterval:
                errors[CONF_DATA_INTERVAL] = "invalid_interval"
            else:
                return self.async_create_entry(
                    title=self.config_entry.title, data=user_input
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DATA_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_DATA_INTERVAL, DEFAULT_DATA_INTERVAL
                        ),
                    ): vol.In(ENERGYID_INTERVALS),
                    vol.Required(
                        CONF_UPLOAD_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_UPLOAD_INTERVAL, DEFAULT_UPLOAD_INTERVAL
                        ),
                    ): int,
                }
            ),
            errors=errors,
        )


class InvalidInterval(HomeAssistantError):
    """Error to indicate there is invalid interval."""
