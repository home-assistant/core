"""Config flow for the HEMS echonet lite integration."""

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
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.network import is_ipv4_address

from .const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    CONF_POLL_INTERVAL,
    DEFAULT_INTERFACE,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)


class EchonetLiteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ECHONET Lite.

    ConfigFlow handles network interface selection only.
    Other options are managed in OptionsFlow.
    """

    VERSION = 1
    MINOR_VERSION = 0

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EchonetLiteOptionsFlow:
        """Get the options flow for this handler."""
        return EchonetLiteOptionsFlow()

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step (UI setup)."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

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
            entry.options.get(CONF_INTERFACE, DEFAULT_INTERFACE)
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
                data={},
                options=_build_default_options(interface),
            )
        # Preserve existing options, only update interface
        new_options = dict(entry.options)
        new_options[CONF_INTERFACE] = interface
        return self.async_update_reload_and_abort(entry, options=new_options)

    async def async_step_import(
        self, import_info: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle automatic setup during startup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Validate interface from external source (may be invalid)
        interface = DEFAULT_INTERFACE
        if import_info and (candidate := import_info.get(CONF_INTERFACE)):
            if _is_valid_interface(candidate):
                interface = candidate
            else:
                _LOGGER.debug(
                    "Ignoring invalid interface '%s' during import", candidate
                )

        if error := await self._async_test_multicast(interface):
            return self.async_abort(reason=error)

        await self.async_set_unique_id(UNIQUE_ID)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="HEMS",
            data={},
            options=_build_default_options(interface),
        )

    async def _async_test_multicast(self, interface: str) -> str | None:
        """Test multicast socket can be created. Returns error key or None."""
        try:
            protocol = await create_multicast_socket(interface, lambda *_: None)
            protocol.close()
        except OSError:
            return "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception during network validation")
            return "unknown"
        else:
            return None


class EchonetLiteOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for ECHONET Lite.

    OptionsFlow manages polling interval and experimental features.
    Network interface is configured in ConfigFlow/Reconfigure.
    """

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Preserve interface from existing options
            new_options = {
                CONF_INTERFACE: self.config_entry.options.get(
                    CONF_INTERFACE, DEFAULT_INTERFACE
                ),
                CONF_POLL_INTERVAL: user_input.get(
                    CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                ),
                CONF_ENABLE_EXPERIMENTAL: user_input.get(
                    CONF_ENABLE_EXPERIMENTAL, False
                ),
            }
            return self.async_create_entry(title="", data=new_options)

        current_poll = self.config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        current_experimental = self.config_entry.options.get(
            CONF_ENABLE_EXPERIMENTAL, False
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): (
                    NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_POLL_INTERVAL,
                            max=MAX_POLL_INTERVAL,
                            step=1,
                            unit_of_measurement="seconds",
                            mode=NumberSelectorMode.BOX,
                        )
                    )
                ),
                vol.Optional(
                    CONF_ENABLE_EXPERIMENTAL, default=current_experimental
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _build_default_options(interface: str) -> dict[str, Any]:
    """Build default options with the specified interface."""
    return {
        CONF_INTERFACE: interface,
        CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
        CONF_ENABLE_EXPERIMENTAL: False,
    }


def _is_valid_interface(value: Any) -> bool:
    """Check if value is a valid interface (DEFAULT_INTERFACE or IPv4)."""
    if not isinstance(value, str):
        return False
    return value == DEFAULT_INTERFACE or is_ipv4_address(value)


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
