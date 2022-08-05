"""Config flow for Switchbot."""
from __future__ import annotations

import logging
from typing import Any

from switchbot import SwitchBotAdvertisement, parse_advertisement_data
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT, DOMAIN, SUPPORTED_MODEL_TYPES

_LOGGER = logging.getLogger(__name__)


def format_unique_id(address: str) -> str:
    """Format the unique ID for a switchbot."""
    return address.replace(":", "").lower()


class SwitchbotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Switchbot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SwitchbotOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SwitchbotOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        self._discovered_adv: SwitchBotAdvertisement | None = None
        self._discovered_advs: dict[str, SwitchBotAdvertisement] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        await self.async_set_unique_id(format_unique_id(discovery_info.address))
        self._abort_if_unique_id_configured()
        parsed = parse_advertisement_data(
            discovery_info.device, discovery_info.advertisement
        )
        if not parsed or parsed.data.get("modelName") not in SUPPORTED_MODEL_TYPES:
            return self.async_abort(reason="not_supported")
        self._discovered_adv = parsed
        data = parsed.data
        self.context["title_placeholders"] = {
            "name": data["modelName"],
            "address": discovery_info.address,
        }
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(
                format_unique_id(address), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            user_input[CONF_SENSOR_TYPE] = SUPPORTED_MODEL_TYPES[
                self._discovered_advs[address].data["modelName"]
            ]
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        if discovery := self._discovered_adv:
            self._discovered_advs[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery_info in async_discovered_service_info(self.hass):
                address = discovery_info.address
                if (
                    format_unique_id(address) in current_addresses
                    or address in self._discovered_advs
                ):
                    continue
                parsed = parse_advertisement_data(
                    discovery_info.device, discovery_info.advertisement
                )
                if parsed and parsed.data.get("modelName") in SUPPORTED_MODEL_TYPES:
                    self._discovered_advs[address] = parsed

        if not self._discovered_advs:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        address: f"{parsed.data['modelName']} ({address})"
                        for address, parsed in self._discovered_advs.items()
                    }
                ),
                vol.Required(CONF_NAME): str,
                vol.Optional(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )


class SwitchbotOptionsFlowHandler(OptionsFlow):
    """Handle Switchbot options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Switchbot options."""
        if user_input is not None:
            # Update common entity options for all other entities.
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_RETRY_COUNT,
                default=self.config_entry.options.get(
                    CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
                ),
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
