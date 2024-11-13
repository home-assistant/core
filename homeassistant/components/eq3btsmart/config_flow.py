"""Config flow for eQ-3 Bluetooth Smart thermostats."""

from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_MAC
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util import slugify

from .const import (
    CONF_CURRENT_TEMP_SELECTOR,
    CONF_EXTERNAL_TEMP_SENSOR,
    CONF_TARGET_TEMP_SELECTOR,
    DEFAULT_CURRENT_TEMP_SELECTOR,
    DEFAULT_TARGET_TEMP_SELECTOR,
    DOMAIN,
    CurrentTemperatureSelector,
    TargetTemperatureSelector,
)
from .coordinator import Eq3ConfigEntry
from .schemas import SCHEMA_MAC


class EQ3ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for eQ-3 Bluetooth Smart thermostats."""

    def __init__(self) -> None:
        """Initialize the config flow."""

        self.mac_address: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors or None,
            )

        mac_address = format_mac(user_input[CONF_MAC])

        if not validate_mac(mac_address):
            errors[CONF_MAC] = "invalid_mac_address"
            return self.async_show_form(
                step_id="user",
                data_schema=SCHEMA_MAC,
                errors=errors,
            )

        await self.async_set_unique_id(mac_address)
        self._abort_if_unique_id_configured(updates=user_input)

        # We can not validate if this mac actually is an eQ-3 thermostat,
        # since the thermostat probably is not advertising right now.
        return self.async_create_entry(title=slugify(mac_address), data={})

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle bluetooth discovery."""

        self.mac_address = format_mac(discovery_info.address)

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        self.context.update({"title_placeholders": {CONF_MAC: self.mac_address}})

        return await self.async_step_init()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle flow start."""

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={CONF_MAC: self.mac_address},
            )

        await self.async_set_unique_id(self.mac_address)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=slugify(self.mac_address),
            data=user_input,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Eq3ConfigEntry,
    ) -> OptionsFlow:
        """Create the options flow."""

        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Options flow for eQ-3 Bluetooth Smart thermostats."""

    def __init__(self, entry: Eq3ConfigEntry) -> None:
        """Initialize the options flow."""

        self._entry = entry
        self._last_rendered_current_temp_selector = entry.options.get(
            CONF_CURRENT_TEMP_SELECTOR, DEFAULT_CURRENT_TEMP_SELECTOR
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        options = self._entry.options.copy()

        if user_input is not None:
            if (
                user_input[CONF_CURRENT_TEMP_SELECTOR]
                != CurrentTemperatureSelector.ENTITY
                or user_input[CONF_CURRENT_TEMP_SELECTOR]
                == self._last_rendered_current_temp_selector
            ):
                return self.async_create_entry(title="", data=user_input)

            self._last_rendered_current_temp_selector = user_input[
                CONF_CURRENT_TEMP_SELECTOR
            ]

            options = {
                CONF_CURRENT_TEMP_SELECTOR: user_input[CONF_CURRENT_TEMP_SELECTOR],
                CONF_TARGET_TEMP_SELECTOR: user_input[CONF_TARGET_TEMP_SELECTOR],
                CONF_EXTERNAL_TEMP_SENSOR: user_input.get(
                    CONF_EXTERNAL_TEMP_SENSOR, None
                ),
            }

        suggested_values = options.copy()
        if CONF_EXTERNAL_TEMP_SENSOR not in suggested_values:
            suggested_values[CONF_EXTERNAL_TEMP_SENSOR] = None

        schema = self.add_suggested_values_to_schema(
            vol.Schema(options_schema(options)), suggested_values
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


def options_schema(
    options: dict[str, Any] | MappingProxyType[str, Any],
) -> dict[vol.Marker, selector.Selector[Any]]:
    """Return the options schema for the eq3btsmart integration."""

    current_temp_selectors = [
        selector.SelectOptionDict(
            label="",
            value=CurrentTemperatureSelector.NOTHING,
        ),
        selector.SelectOptionDict(
            label="",
            value=CurrentTemperatureSelector.UI,
        ),
        selector.SelectOptionDict(
            label="",
            value=CurrentTemperatureSelector.DEVICE,
        ),
        selector.SelectOptionDict(
            label="",
            value=CurrentTemperatureSelector.VALVE,
        ),
        selector.SelectOptionDict(
            label="",
            value=CurrentTemperatureSelector.ENTITY,
        ),
    ]

    target_temp_selectors = [
        selector.SelectOptionDict(
            label="",
            value=TargetTemperatureSelector.TARGET,
        ),
        selector.SelectOptionDict(
            label="",
            value=TargetTemperatureSelector.LAST_REPORTED,
        ),
    ]

    schema: dict[vol.Marker, selector.Selector[Any]] = {
        vol.Required(
            CONF_CURRENT_TEMP_SELECTOR, default=DEFAULT_CURRENT_TEMP_SELECTOR
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=current_temp_selectors,
                translation_key=CONF_CURRENT_TEMP_SELECTOR,
            ),
        ),
        vol.Required(
            CONF_TARGET_TEMP_SELECTOR, default=DEFAULT_TARGET_TEMP_SELECTOR
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=target_temp_selectors, translation_key=CONF_TARGET_TEMP_SELECTOR
            ),
        ),
    }

    if options.get(CONF_CURRENT_TEMP_SELECTOR) == CurrentTemperatureSelector.ENTITY:
        schema.update(
            {
                vol.Required(
                    CONF_EXTERNAL_TEMP_SENSOR,
                    default=options.get(CONF_EXTERNAL_TEMP_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=SENSOR_DOMAIN,
                        device_class=SensorDeviceClass.TEMPERATURE,
                    )
                )
            }
        )

    return schema


def validate_mac(mac: str) -> bool:
    """Return whether or not given value is a valid MAC address."""

    return bool(
        mac
        and len(mac) == 17
        and mac.count(":") == 5
        and all(int(part, 16) < 256 for part in mac.split(":") if part)
    )
