"""Config flow for ViCare integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from PyViCare.PyViCareUtils import (
    PyViCareInvalidConfigurationError,
    PyViCareInvalidCredentialsError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ACTIVE_DEVICES,
    CONF_HEATING_TYPE,
    DEFAULT_HEATING_TYPE,
    DOMAIN,
    VICARE_NAME,
    HeatingType,
)
from .utils import get_device_list, login

_LOGGER = logging.getLogger(__name__)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
    }
)

USER_SCHEMA = REAUTH_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_HEATING_TYPE, default=DEFAULT_HEATING_TYPE.value): vol.In(
            [e.value for e in HeatingType]
        ),
    }
)


def _get_option_list(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> list[SelectOptionDict]:
    device_list = get_device_list(hass, entry.data)
    return [
        # we cannot always use device_config.getConfig().serial as it returns the gateway serial for all connected devices
        SelectOptionDict(
            value=device_config.getConfig().serial,
            label=f"{device_config.getConfig().serial} ({device_config.getModel()})",
        )
        if device_config.getModel() == "Heatbox1"
        # we cannot always use device.getSerial() either as there is a different API endpoint used for gateways that does not provide the serial (yet)
        else SelectOptionDict(
            value=device_config.asAutoDetectDevice().getSerial(),
            label=f"{device_config.asAutoDetectDevice().getSerial()} ({device_config.getModel()})",
        )
        for device_config in device_list
    ]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ViCare."""

    VERSION = 2
    entry: config_entries.ConfigEntry | None
    available_devices: list[SelectOptionDict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Invoke when a user initiates a flow via the user interface."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.available_devices = await self.hass.async_add_executor_job(
                    _get_option_list,
                    self.hass,
                    user_input,
                )
            except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError):
                errors["base"] = "invalid_auth"
            else:
                if len(self.available_devices) == 1:
                    return self.async_create_entry(
                        title=VICARE_NAME,
                        data={
                            **user_input,
                            CONF_ACTIVE_DEVICES: self.available_devices[0]["value"],
                        },
                    )
                return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which device to show."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        suggested_values: Mapping[str, Any] = {}
        if self.entry is not None:
            suggested_values = {
                CONF_ACTIVE_DEVICES: self.entry.data[CONF_ACTIVE_DEVICES]
            }

        schema = (
            vol.Schema(
                {
                    vol.Required(CONF_ACTIVE_DEVICES): SelectSelector(
                        SelectSelectorConfig(
                            options=self.available_devices,
                            multiple=False,
                            mode=SelectSelectorMode.LIST,
                        ),
                    ),
                }
            ),
        )

        return self.async_show_form(
            step_id="select",
            data_schema=self.add_suggested_values_to_schema(
                schema,
                suggested_values,
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with ViCare."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with ViCare."""
        errors: dict[str, str] = {}
        assert self.entry is not None

        if user_input:
            data = {
                **self.entry.data,
                **user_input,
            }

            try:
                await self.hass.async_add_executor_job(login, self.hass, data)
            except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError):
                errors["base"] = "invalid_auth"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, self.entry.data
            ),
            errors=errors,
        )

    async def async_step_dhcp(self, discovery_info: dhcp.DhcpServiceInfo) -> FlowResult:
        """Invoke when a Viessmann MAC address is discovered on the network."""
        formatted_mac = format_mac(discovery_info.macaddress)
        _LOGGER.info("Found device with mac %s", formatted_mac)

        await self.async_set_unique_id(formatted_mac)
        self._abort_if_unique_id_configured()

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        try:
            options_list: list[
                SelectOptionDict
            ] = await self.hass.async_add_executor_job(
                _get_option_list, self.hass, self.entry
            )
        except (PyViCareInvalidConfigurationError, PyViCareInvalidCredentialsError):
            errors["base"] = "invalid_auth"

        suggested_values: Mapping[str, Any] = {
            CONF_ACTIVE_DEVICES: self.entry.data[CONF_ACTIVE_DEVICES]
        }

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_ACTIVE_DEVICES): SelectSelector(
                            SelectSelectorConfig(
                                options=options_list,
                                multiple=False,
                                mode=SelectSelectorMode.LIST,
                            ),
                        ),
                    }
                ),
                suggested_values,
            ),
            errors=errors,
        )
