"""Config flow for Acaia integration."""

import logging
from typing import Any, override

from aioacaia.discovery import is_new_scale
from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError, AcaiaUnknownDevice
import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_IDLE_TIMEOUT,
    CONF_IS_NEW_STYLE_SCALE,
    DEFAULT_IDLE_TIMEOUT,
    DOMAIN,
)
from .coordinator import AcaiaConfigEntry

_LOGGER = logging.getLogger(__name__)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_IDLE_TIMEOUT, default=DEFAULT_IDLE_TIMEOUT
        ): probatio.All(
            NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=120,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.MINUTES,
                )
            ),
            probatio.Coerce(int),
        ),
    }
)


class AcaiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for acaia."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered: dict[str, Any] = {}
        self._discovered_devices: dict[str, str] = {}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: AcaiaConfigEntry) -> AcaiaOptionsFlow:
        """Get the options flow for this handler."""
        return AcaiaOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_ADDRESS]
            try:
                is_new_style_scale = await is_new_scale(mac)
            except AcaiaDeviceNotFound:
                errors["base"] = "device_not_found"
            except AcaiaError:
                _LOGGER.exception("Error occurred while connecting to the scale")
                errors["base"] = "unknown"
            except AcaiaUnknownDevice:
                return self.async_abort(reason="unsupported_device")
            else:
                await self.async_set_unique_id(format_mac(mac))
                self._abort_if_unique_id_configured()

            if not errors:
                return self.async_create_entry(
                    title=self._discovered_devices[mac],
                    data={
                        CONF_ADDRESS: mac,
                        CONF_IS_NEW_STYLE_SCALE: is_new_style_scale,
                    },
                )

        for device in async_discovered_service_info(self.hass):
            self._discovered_devices[device.address] = device.name

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        options = [
            SelectOptionDict(
                value=device_mac,
                label=f"{device_name} ({device_mac})",
            )
            for device_mac, device_name in self._discovered_devices.items()
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a discovered Bluetooth device."""

        self._discovered[CONF_ADDRESS] = discovery_info.address
        self._discovered[CONF_NAME] = discovery_info.name

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        try:
            self._discovered[CONF_IS_NEW_STYLE_SCALE] = await is_new_scale(
                discovery_info.address
            )
        except AcaiaDeviceNotFound:
            _LOGGER.debug("Device not found during discovery")
            return self.async_abort(reason="device_not_found")
        except AcaiaError:
            _LOGGER.debug(
                "Error occurred while connecting to the scale during discovery",
                exc_info=True,
            )
            return self.async_abort(reason="unknown")
        except AcaiaUnknownDevice:
            _LOGGER.debug("Unsupported device during discovery")
            return self.async_abort(reason="unsupported_device")

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle confirmation of Bluetooth discovery."""

        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered[CONF_NAME],
                data={
                    CONF_ADDRESS: self._discovered[CONF_ADDRESS],
                    CONF_IS_NEW_STYLE_SCALE: self._discovered[CONF_IS_NEW_STYLE_SCALE],
                },
            )

        self.context["title_placeholders"] = placeholders = {
            "name": self._discovered[CONF_NAME]
        }

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
        )


class AcaiaOptionsFlow(OptionsFlowWithReload):
    """Handle the connection options of an Acaia scale."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
