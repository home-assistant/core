"""Config flow for La Marzocco integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientSession
from pylamarzocco import LaMarzoccoCloudClient
from pylamarzocco.exceptions import AuthFail, RequestNotSuccessful
from pylamarzocco.models import Thing
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import CONF_USE_BLUETOOTH, DOMAIN
from .coordinator import LaMarzoccoConfigEntry

CONF_MACHINE = "machine"
BT_MODEL_PREFIXES = ("MICRA", "MINI", "GS3")

_LOGGER = logging.getLogger(__name__)


class LmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 3

    _client: ClientSession

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}
        self._things: dict[str, Thing] = {}
        self._discovered: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors = {}

        if user_input:
            data: dict[str, Any] = {}
            if self.source == SOURCE_REAUTH:
                data = dict(self._get_reauth_entry().data)
            data = {
                **data,
                **user_input,
            }

            self._client = async_create_clientsession(self.hass)
            cloud_client = LaMarzoccoCloudClient(
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
                client=self._client,
            )
            try:
                things = await cloud_client.list_things()
            except AuthFail:
                _LOGGER.debug("Server rejected login credentials")
                errors["base"] = "invalid_auth"
            except RequestNotSuccessful as exc:
                _LOGGER.error("Error connecting to server: %s", exc)
                errors["base"] = "cannot_connect"
            else:
                self._things = {thing.serial_number: thing for thing in things}
                if not self._things:
                    errors["base"] = "no_machines"

            if not errors:
                self._config = data
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=data
                    )
                if self._discovered:
                    if self._discovered[CONF_MACHINE] not in self._things:
                        errors["base"] = "machine_not_found"
                    else:
                        # store discovered connection address
                        if CONF_MAC in self._discovered:
                            self._config[CONF_MAC] = self._discovered[CONF_MAC]
                        if CONF_ADDRESS in self._discovered:
                            self._config[CONF_ADDRESS] = self._discovered[CONF_ADDRESS]

                        return await self.async_step_machine_selection(
                            user_input={CONF_MACHINE: self._discovered[CONF_MACHINE]}
                        )
            if not errors:
                return await self.async_step_machine_selection()

        placeholders: dict[str, str] | None = None
        if self._discovered:
            self.context["title_placeholders"] = placeholders = {
                CONF_NAME: self._discovered[CONF_MACHINE]
            }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.EMAIL, autocomplete="username"
                        )
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_machine_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let user select machine to connect to."""
        errors: dict[str, str] = {}
        if user_input:
            if not self._discovered:
                serial_number = user_input[CONF_MACHINE]
                if self.source != SOURCE_RECONFIGURE:
                    await self.async_set_unique_id(serial_number)
                    self._abort_if_unique_id_configured()
            else:
                serial_number = self._discovered[CONF_MACHINE]

            selected_device = self._things[serial_number]

            if not errors:
                if self.source == SOURCE_RECONFIGURE:
                    for service_info in async_discovered_service_info(self.hass):
                        if service_info.name.startswith(BT_MODEL_PREFIXES):
                            self._discovered[service_info.name] = service_info.address

                    if self._discovered:
                        return await self.async_step_bluetooth_selection()
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data_updates=self._config,
                    )

                return self.async_create_entry(
                    title=selected_device.name,
                    data={
                        **self._config,
                        CONF_TOKEN: self._things[serial_number].ble_auth_token,
                    },
                )

        machine_options = [
            SelectOptionDict(
                value=thing.serial_number,
                label=f"{thing.name} ({thing.serial_number})",
            )
            for thing in self._things.values()
        ]

        machine_selection_schema = vol.Schema(
            {
                vol.Required(
                    CONF_MACHINE, default=machine_options[0]["value"]
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=machine_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="machine_selection",
            data_schema=machine_selection_schema,
            errors=errors,
        )

    async def async_step_bluetooth_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Bluetooth device selection."""

        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates={
                    CONF_MAC: user_input[CONF_MAC],
                },
            )

        bt_options = [
            SelectOptionDict(
                value=device_mac,
                label=f"{device_name} ({device_mac})",
            )
            for device_name, device_mac in self._discovered.items()
        ]

        return self.async_show_form(
            step_id="bluetooth_selection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MAC): SelectSelector(
                        SelectSelectorConfig(
                            options=bt_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                },
            ),
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by discovery over Bluetooth."""
        address = discovery_info.address
        name = discovery_info.name

        _LOGGER.debug(
            "Discovered La Marzocco machine %s through Bluetooth at address %s",
            name,
            address,
        )

        self._discovered[CONF_NAME] = name
        self._discovered[CONF_MAC] = address

        serial = name.split("_")[1]
        self._discovered[CONF_MACHINE] = serial

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured()

        return await self.async_step_user()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle discovery via dhcp."""

        serial = discovery_info.hostname.upper()

        await self.async_set_unique_id(serial)
        self._abort_if_unique_id_configured(
            updates={
                CONF_ADDRESS: discovery_info.macaddress,
            }
        )
        self._async_abort_entries_match({CONF_ADDRESS: discovery_info.macaddress})

        _LOGGER.debug(
            "Discovered La Marzocco machine %s through DHCP at address %s",
            discovery_info.hostname,
            discovery_info.ip,
        )

        self._discovered[CONF_NAME] = discovery_info.hostname
        self._discovered[CONF_MACHINE] = serial
        self._discovered[CONF_ADDRESS] = discovery_info.macaddress

        return await self.async_step_user()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        return await self.async_step_user(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Perform reconfiguration of the config entry."""
        if not user_input:
            reconfigure_entry = self._get_reconfigure_entry()
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_USERNAME, default=reconfigure_entry.data[CONF_USERNAME]
                        ): TextSelector(
                            TextSelectorConfig(
                                type=TextSelectorType.EMAIL, autocomplete="username"
                            ),
                        ),
                        vol.Required(
                            CONF_PASSWORD, default=reconfigure_entry.data[CONF_PASSWORD]
                        ): TextSelector(
                            TextSelectorConfig(
                                type=TextSelectorType.PASSWORD,
                                autocomplete="current-password",
                            ),
                        ),
                    }
                ),
            )

        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: LaMarzoccoConfigEntry,
    ) -> LmOptionsFlowHandler:
        """Create the options flow."""
        return LmOptionsFlowHandler()


class LmOptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options for the custom component."""
        if user_input:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USE_BLUETOOTH,
                    default=self.config_entry.options.get(CONF_USE_BLUETOOTH, True),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
