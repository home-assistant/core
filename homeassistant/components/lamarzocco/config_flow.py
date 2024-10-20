"""Config flow for La Marzocco integration."""

from collections.abc import Mapping
import logging
from typing import Any

from lmcloud.client_cloud import LaMarzoccoCloudClient
from lmcloud.client_local import LaMarzoccoLocalClient
from lmcloud.exceptions import AuthFail, RequestNotSuccessful
from lmcloud.models import LaMarzoccoDeviceInfo
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_USE_BLUETOOTH, DOMAIN

CONF_MACHINE = "machine"

_LOGGER = logging.getLogger(__name__)


class LmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for La Marzocco."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}
        self._fleet: dict[str, LaMarzoccoDeviceInfo] = {}
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
                **self._discovered,
            }

            cloud_client = LaMarzoccoCloudClient(
                username=data[CONF_USERNAME],
                password=data[CONF_PASSWORD],
            )
            try:
                self._fleet = await cloud_client.get_customer_fleet()
            except AuthFail:
                _LOGGER.debug("Server rejected login credentials")
                errors["base"] = "invalid_auth"
            except RequestNotSuccessful as exc:
                _LOGGER.error("Error connecting to server: %s", exc)
                errors["base"] = "cannot_connect"
            else:
                if not self._fleet:
                    errors["base"] = "no_machines"

            if not errors:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=data
                    )
                if self._discovered:
                    if self._discovered[CONF_MACHINE] not in self._fleet:
                        errors["base"] = "machine_not_found"
                    else:
                        self._config = data
                        return self.async_show_form(
                            step_id="machine_selection",
                            data_schema=vol.Schema(
                                {vol.Optional(CONF_HOST): cv.string}
                            ),
                        )

            if not errors:
                self._config = data
                return await self.async_step_machine_selection()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
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

            selected_device = self._fleet[serial_number]

            # validate local connection if host is provided
            if user_input.get(CONF_HOST):
                if not await LaMarzoccoLocalClient.validate_connection(
                    client=get_async_client(self.hass),
                    host=user_input[CONF_HOST],
                    token=selected_device.communication_key,
                ):
                    errors[CONF_HOST] = "cannot_connect"
                else:
                    self._config[CONF_HOST] = user_input[CONF_HOST]

            if not errors:
                if self.source == SOURCE_RECONFIGURE:
                    for service_info in async_discovered_service_info(self.hass):
                        self._discovered[service_info.name] = service_info.address

                    if self._discovered:
                        return await self.async_step_bluetooth_selection()

                return self.async_create_entry(
                    title=selected_device.name,
                    data={
                        **self._config,
                        CONF_NAME: selected_device.name,
                        CONF_MODEL: selected_device.model,
                        CONF_TOKEN: selected_device.communication_key,
                    },
                )

        machine_options = [
            SelectOptionDict(
                value=device.serial_number,
                label=f"{device.model} ({device.serial_number})",
            )
            for device in self._fleet.values()
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
                vol.Optional(CONF_HOST): cv.string,
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
                data={
                    **self._config,
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
                            CONF_USERNAME,
                            default=reconfigure_entry.data[CONF_USERNAME],
                        ): str,
                        vol.Required(
                            CONF_PASSWORD,
                            default=reconfigure_entry.data[CONF_PASSWORD],
                        ): str,
                    }
                ),
            )

        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""
        return LmOptionsFlowHandler(config_entry)


class LmOptionsFlowHandler(OptionsFlowWithConfigEntry):
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
                    default=self.options.get(CONF_USE_BLUETOOTH, True),
                ): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
