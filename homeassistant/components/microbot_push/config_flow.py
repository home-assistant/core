"""Adds config flow for MicroBot."""
from __future__ import annotations

import logging
import re
from typing import Any

from bleak.backends.device import BLEDevice
from microbot import (  # pylint: disable=import-error
    MicroBotAdvertisement,
    MicroBotApiClient,
    parse_advertisement_data,
)
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_BDADDR, CONF_NAME, DEFAULT_RETRY_COUNT, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__package__)

class MicroBotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for MicroBot."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self._errors = {}
        self._discovered_adv: MicroBotAdvertisement | None = None
        self._discovered_advs: dict[str, MicroBotAdvertisement] = {}
        self._client: Any | None
        self._ble_device: BLEDevice | None
        self._name = None
        self._bdaddr: str

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        parsed = parse_advertisement_data(
            discovery_info.device, discovery_info.advertisement
        )
        self._discovered_adv = parsed
        data = parsed.data
        self.context["title_placeholders"] = {
            "name": data["local_name"],
            "address": discovery_info.address,
        }
        return await self.async_step_init()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Check if paired."""
        errors: dict[str, str] = {}

        if discovery := self._discovered_adv:
            self._discovered_advs[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery_info in async_discovered_service_info(self.hass):
                address = discovery_info.address
                if (
                    address in current_addresses
                    or address in self._discovered_advs
                ):
                    continue
                parsed = parse_advertisement_data(
                    discovery_info.device, discovery_info.advertisement
                )
                if parsed:
                    self._discovered_advs[address] = parsed

        if not self._discovered_advs:
            return self.async_abort(reason="no_unconfigured_devices")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_BDADDR): vol.In(
                    {
                        address: f"{parsed.data['local_name']} ({address})"
                        for address, parsed in self._discovered_advs.items()
                    }
                ),
                vol.Required(CONF_NAME): str,
            }
        )

        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._bdaddr = user_input[CONF_BDADDR]
            await self.async_set_unique_id(
                self._bdaddr, raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            self._ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self._bdaddr.upper()
            )
            if not self._ble_device:
                raise ConfigEntryNotReady(
                    f"Could not find MicroBot with address {self._bdaddr}"
                )
            conf = (
                self.hass.config.path()
                + "/.storage/microbot-"
                + re.sub("[^a-f0-9]", "", self._bdaddr.lower())
                + ".conf"
            )
            self._client = MicroBotApiClient(
                device=self._ble_device,
                config=conf,
                retry_count=DEFAULT_RETRY_COUNT,
            )
            token = self._client.hasToken()
            if not token:
                return await self.async_step_link()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

    async def async_step_link(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Given a configured host, will ask the user to press the button to pair."""
        errors: dict[str, str] = {}
        assert self._client is not None
        token = self._client.hasToken()
        if user_input is None:
            try:
                await self._client.connect(init=True)
            except Exception as e
                _LOGGER.exception("Error connecting with MicroBot: %s", e)
                errors["base"] = "linking"
            return self.async_show_form(step_id="link")

        if not token:
            errors["base"] = "linking"

        if errors:
            return self.async_show_form(step_id="link", errors=errors)

        user_input[CONF_BDADDR] = self._bdaddr

        return self.async_create_entry(title=self._name, data=user_input)
