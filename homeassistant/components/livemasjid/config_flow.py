"""Config flow for Livemasjid integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant as hass, callback
from homeassistant.helpers import entity_registry

from .const import (
    ALTERNATE_DEVICES,
    ALTERNATE_STREAMS,
    ALTERNATE_SUBSCRIPTIONS,
    DEFAULT_SUBSCRIPTION,
    DOMAIN,
    NAME,
    PRIMARY_DEVICE,
    PRIMARY_SUBSCRIPTION,
    SUBSCRIPTIONS,
)

_LOGGER = logging.getLogger(__name__)


def list_to_str(data: list[Any]) -> str:
    """Convert an int list to a string."""
    return ", ".join([str(i) for i in data])


def str_to_list(data: str) -> list[str]:
    """Convert a string to a list."""
    spaces_removed_list = [s.replace(" ", "") for s in data.split(",")]
    return [item for item in spaces_removed_list if item != ""]


def options_data(user_input: dict) -> dict:
    """Return options dict."""
    primary_subscription = user_input.get(PRIMARY_SUBSCRIPTION, "")
    alternate_subscriptions = str_to_list(user_input.get(ALTERNATE_SUBSCRIPTIONS, ""))
    alternate_streams = str_to_list(user_input.get(ALTERNATE_STREAMS, ""))
    alternate_devices = str_to_list(user_input.get(ALTERNATE_DEVICES, ""))
    subscriptions = set(
        [primary_subscription] + alternate_subscriptions + alternate_streams
    )

    return {
        **user_input,
        ALTERNATE_SUBSCRIPTIONS: list(set(alternate_subscriptions)),
        ALTERNATE_STREAMS: list(set(alternate_streams)),
        ALTERNATE_DEVICES: list(set(alternate_devices)),
        SUBSCRIPTIONS: list(subscriptions),
    }


class LivemasjidFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Livemasjid."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return LivemasjidOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(step_id="user")

        return self.async_create_entry(title=NAME, data=user_input)

    async def async_step_import(self, import_config):
        """Import from config."""
        return await self.async_step_user(user_input=import_config)


def get_options_schema(options, subscription_items, registry_entities):
    """Get options schema."""
    return {
        vol.Optional(
            PRIMARY_SUBSCRIPTION,
            default=options.get(PRIMARY_SUBSCRIPTION, DEFAULT_SUBSCRIPTION),
        ): vol.In(subscription_items.keys()),
        vol.Optional(
            ALTERNATE_SUBSCRIPTIONS,
            default=", ".join(options.get(ALTERNATE_SUBSCRIPTIONS, [])),
        ): str,
        vol.Optional(
            ALTERNATE_STREAMS, default=", ".join(options.get(ALTERNATE_STREAMS, []))
        ): str,
        vol.Optional(PRIMARY_DEVICE, default=options.get(PRIMARY_DEVICE, ""),): vol.In(
            [
                v.entity_id
                for k, v in registry_entities.entities.items()
                if "media_player." in v.entity_id
            ]
        ),
        vol.Optional(
            ALTERNATE_DEVICES, default=", ".join(options.get(ALTERNATE_DEVICES, []))
        ): str,
    }


class LivemasjidOptionsFlowHandler(hass, config_entries.OptionsFlow):
    """Handle Islamic Prayer client options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=options_data(user_input))

        lm = self.hass.data[DOMAIN][self.config_entry.entry_id].get("client")

        subscriptions = lm.get_status()

        registry_entities = await entity_registry.async_get_registry(self.hass)

        options = get_options_schema(
            self.config_entry.options, subscriptions, registry_entities
        )

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
