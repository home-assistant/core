"""Config flow for the HEMS Echonet Lite integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyhems import create_multicast_socket
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_ENABLE_EXPERIMENTAL, CONF_INTERFACE, DEFAULT_INTERFACE, DOMAIN
from .types import EchonetLiteConfigEntry

_LOGGER = logging.getLogger(__name__)


class EchonetLiteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ECHONET Lite.

    ConfigFlow handles network interface selection only.
    Other options are managed in OptionsFlow.
    """

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: EchonetLiteConfigEntry,
    ) -> EchonetLiteOptionsFlow:
        """Get the options flow for this handler."""
        return EchonetLiteOptionsFlow()

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step (UI setup)."""
        return await self._async_handle_interface_step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the network interface."""
        return await self._async_handle_interface_step("reconfigure", user_input)

    async def _async_handle_interface_step(
        self, step_id: str, user_input: Mapping[str, Any] | None
    ) -> config_entries.ConfigFlowResult:
        """Handle interface selection for both user and reconfigure steps."""
        entry = self._get_reconfigure_entry() if step_id == "reconfigure" else None
        current_interface = (
            entry.data.get(CONF_INTERFACE, DEFAULT_INTERFACE)
            if entry
            else DEFAULT_INTERFACE
        )

        interface_options = await _async_get_interface_options(self.hass)
        valid_interfaces = {opt["value"] for opt in interface_options}
        errors: dict[str, str] = {}

        if user_input is not None:
            interface = user_input.get(CONF_INTERFACE, DEFAULT_INTERFACE)

            if interface not in valid_interfaces:
                errors[CONF_INTERFACE] = "invalid_interface"
            elif error := await self._async_test_multicast(interface):
                errors["base"] = error
            else:
                return self._async_finish_interface_step(entry, interface)

        schema = vol.Schema(
            {
                vol.Optional(CONF_INTERFACE, default=current_interface): (
                    SelectSelector(
                        SelectSelectorConfig(
                            options=interface_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                ),
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    def _async_finish_interface_step(
        self,
        entry: config_entries.ConfigEntry | None,
        interface: str,
    ) -> config_entries.ConfigFlowResult:
        """Finish interface step with create or update."""
        if entry is None:
            return self.async_create_entry(
                title="HEMS",
                data={CONF_INTERFACE: interface},
                options=_build_default_options(),
            )
        # Update interface in data; preserve existing options
        return self.async_update_reload_and_abort(
            entry, data={CONF_INTERFACE: interface}
        )

    async def _async_test_multicast(self, interface: str) -> str | None:
        """Test multicast socket can be created. Returns error key or None."""
        try:
            protocol = await create_multicast_socket(interface, lambda *_: None)
            protocol.close()
        except OSError:
            return "cannot_connect"
        else:
            return None


class EchonetLiteOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ECHONET Lite.

    OptionsFlow manages experimental features.
    Network interface is configured in ConfigFlow/Reconfigure.
    """

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_ENABLE_EXPERIMENTAL: user_input.get(
                        CONF_ENABLE_EXPERIMENTAL, False
                    ),
                },
            )

        current_experimental = self.config_entry.options.get(
            CONF_ENABLE_EXPERIMENTAL, False
        )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_EXPERIMENTAL, default=current_experimental
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _build_default_options() -> dict[str, Any]:
    """Build default options."""
    return {
        CONF_ENABLE_EXPERIMENTAL: False,
    }


async def _async_get_interface_options(hass: HomeAssistant) -> list[SelectOptionDict]:
    """Build interface select options from network adapters."""
    options: list[SelectOptionDict] = [
        {"value": DEFAULT_INTERFACE, "label": f"Auto ({DEFAULT_INTERFACE})"}
    ]

    try:
        adapters = await network.async_get_adapters(hass)
        for adapter in adapters:
            if not adapter["enabled"]:
                continue
            name = adapter.get("name", "unknown")
            options.extend(
                {"value": address, "label": f"{name} ({address})"}
                for ipv4 in adapter.get("ipv4", [])
                if (address := ipv4.get("address")) and address != "127.0.0.1"
            )
    except OSError:
        _LOGGER.debug("Failed to enumerate network adapters")

    return options
