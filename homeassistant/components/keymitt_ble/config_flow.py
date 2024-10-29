"""Adds config flow for MicroBot."""

from __future__ import annotations

import logging
from typing import Any

from bleak.backends.device import BLEDevice
from microbot import (
    MicroBotAdvertisement,
    MicroBotApiClient,
    parse_advertisement_data,
    randomid,
)
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS

from .const import DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)


def short_address(address: str) -> str:
    """Convert a Bluetooth address to a short address."""
    results = address.replace("-", ":").split(":")
    return f"{results[0].upper()}{results[1].upper()}"[0:4]


def name_from_discovery(discovery: MicroBotAdvertisement) -> str:
    """Get the name from a discovery."""
    return f'{discovery.data["local_name"]} {short_address(discovery.address)}'


class MicroBotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for MicroBot."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._errors: dict[str, str] = {}
        self._discovered_adv: MicroBotAdvertisement | None = None
        self._discovered_advs: dict[str, MicroBotAdvertisement] = {}
        self._client: MicroBotApiClient | None = None
        self._ble_device: BLEDevice | None = None
        self._name: str | None = None
        self._bdaddr: str | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._ble_device = discovery_info.device
        parsed = parse_advertisement_data(
            discovery_info.device, discovery_info.advertisement
        )
        self._discovered_adv = parsed
        self.context["title_placeholders"] = {
            "name": name_from_discovery(self._discovered_adv),
        }
        return await self.async_step_init()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check if paired."""
        errors: dict[str, str] = {}

        if discovery := self._discovered_adv:
            self._discovered_advs[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery_info in async_discovered_service_info(self.hass):
                self._ble_device = discovery_info.device
                address = discovery_info.address
                if address in current_addresses or address in self._discovered_advs:
                    continue
                parsed = parse_advertisement_data(
                    discovery_info.device, discovery_info.advertisement
                )
                if parsed:
                    self._discovered_adv = parsed
                    self._discovered_advs[address] = parsed

        if not self._discovered_advs:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            self._name = name_from_discovery(self._discovered_adv)
            self._bdaddr = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(self._bdaddr, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return await self.async_step_link()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{parsed.data['local_name']} ({address})"
                            for address, parsed in self._discovered_advs.items()
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Given a configured host, will ask the user to press the button to pair."""
        errors: dict[str, str] = {}
        token = randomid(32)
        self._client = MicroBotApiClient(
            device=self._ble_device,
            token=token,
        )
        assert self._client is not None
        if user_input is None:
            await self._client.connect(init=True)
            return self.async_show_form(step_id="link")

        if not await self._client.is_connected():
            await self._client.connect(init=False)
        if not await self._client.is_connected():
            errors["base"] = "linking"
        else:
            await self._client.disconnect()

        if errors:
            return self.async_show_form(step_id="link", errors=errors)

        assert self._name is not None
        return self.async_create_entry(
            title=self._name,
            data=user_input
            | {
                CONF_ADDRESS: self._bdaddr,
                CONF_ACCESS_TOKEN: token,
            },
        )
