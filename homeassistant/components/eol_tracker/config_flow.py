"""Config flow for the EOL Tracker integration."""

from typing import Any

from eoltracker import EOLClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN

CONF_DEVICE = "input_device"
CONF_VERSION = "version"
CONF_NAME = "custom_device_name"

API_BASE = "https://endoflife.date/api/v1"

"""Config flow for the EOL Tracker integration."""


class EolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the EOL Tracker integration."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.products: list[dict[str, Any]] = []
        self.device_label: str | None = None
        self.device_name: str | None = None
        self.custom_name: str | None = None
        self.label_to_release_name: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step where user selects a device."""
        if not self.products:
            session = async_get_clientsession(self.hass)
            client = EOLClient(session)
            self.products = await client.fetch_all_products()

        label_to_name = {prod["label"]: prod["name"] for prod in self.products}

        if user_input is not None:
            self.device_label = user_input[CONF_DEVICE]
            self.device_name = label_to_name.get(self.device_label)
            if not self.device_name:
                return self.async_abort(reason="invalid_device")
            return await self.async_step_version()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE): vol.In(sorted(label_to_name.keys())),
                }
            ),
        )

    async def async_step_version(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the version step where user selects device version."""
        if not self.device_name:
            return self.async_abort(reason="missing_device")

        session = async_get_clientsession(self.hass)
        client = EOLClient(session)
        self.label_to_release_name = await client.fetch_product_versions(
            self.device_name
        )

        if not self.label_to_release_name:
            return self.async_abort(reason="no_versions_found")

        version_labels = sorted(self.label_to_release_name.keys())

        if user_input is not None:
            selected_label = user_input[CONF_VERSION]
            self.custom_name = user_input.get(CONF_NAME, "")

            release_name = self.label_to_release_name.get(selected_label)
            if not release_name:
                return self.async_abort(reason="invalid_release")

            uri = f"{API_BASE}/products/{self.device_name}/releases/{release_name}"

            await self.async_set_unique_id(uri)
            self._abort_if_unique_id_configured()

            entry_title = self.custom_name or f"{self.device_label} - {selected_label}"

            return self.async_create_entry(
                title=entry_title,
                data={
                    CONF_DEVICE: uri,
                    CONF_VERSION: selected_label,
                    CONF_NAME: self.custom_name,
                },
            )

        return self.async_show_form(
            step_id="version",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VERSION): vol.In(version_labels),
                    vol.Optional(CONF_NAME, default=""): str,
                }
            ),
            description_placeholders={"device": self.device_label or ""},
        )
