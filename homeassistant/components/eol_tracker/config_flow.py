"""Config flow for the EOL Tracker integration."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from eoltracker import EOLClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN

CONF_DEVICE = "input_device"
CONF_NAME = "custom_device_name"

API_BASE = "https://endoflife.date/api/v1"


class EolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the EOL Tracker integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.products: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where a user selects a product."""
        errors: dict[str, str] = {}

        if not self.products:
            try:
                session = async_get_clientsession(self.hass)
                client = EOLClient(session)
                self.products = await client.fetch_all_products()
            except ClientError:
                errors["base"] = "cannot_connect"

        label_to_name = {product["label"]: product["name"] for product in self.products}
        device_labels = sorted(label_to_name)
        if not device_labels:
            errors["base"] = "no_products"

        if user_input is not None:
            device_label = user_input[CONF_DEVICE]
            device_name = label_to_name.get(device_label)
            if not device_name:
                errors["base"] = "invalid_device"
            else:
                uri = f"{API_BASE}/products/{device_label}/releases/latest"

                await self.async_set_unique_id(uri)
                self._abort_if_unique_id_configured()

                custom_name = user_input.get(CONF_NAME, "")
                entry_title = custom_name or device_name

                return self.async_create_entry(
                    title=entry_title,
                    data={
                        CONF_DEVICE: uri,
                        CONF_NAME: custom_name,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(device_labels),
                    vol.Optional(CONF_NAME, default=""): str,
                }
            ),
            errors=errors,
        )
