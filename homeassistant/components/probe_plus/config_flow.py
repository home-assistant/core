"""Config flow for probe_plus integration."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class Discovery:
    """Represents a discovered Bluetooth device.

    Attributes:
        title: The name or title of the discovered device.
        discovery_info: Information about the discovered device.

    """

    title: str
    discovery_info: BluetoothServiceInfo


def title(discovery_info: BluetoothServiceInfo) -> str:
    """Return a title for the discovered device."""
    return f"{discovery_info.name} {discovery_info.address}"


class ProbeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BT Probe."""

    VERSION = 1
    _entry: ConfigEntry

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Discovery] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered BT device: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": title(discovery_info)}
        self._discovered_devices[discovery_info.address] = Discovery(
            title(discovery_info), discovery_info
        )

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the bluetooth confirmation step."""
        if user_input is not None:
            assert self.unique_id
            address: str = self.unique_id
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]
            return self.async_create_entry(
                title=discovery.title,
                data={
                    CONF_ADDRESS: discovery.discovery_info.address,
                },
            )
        self._set_confirm_only()
        assert self.unique_id
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": title(self._discovered_devices[self.unique_id].discovery_info)
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]
            return self.async_create_entry(
                title=discovery.title,
                data=user_input,
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue

            self._discovered_devices[address] = Discovery(
                title(discovery_info), discovery_info
            )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.title
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(titles),
                }
            ),
        )
