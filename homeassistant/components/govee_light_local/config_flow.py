"""Config flow for Govee light local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from ipaddress import AddressValueError, IPv4Address
import logging
from typing import Any

from govee_local_api import GoveeController
import voluptuous as vol

from homeassistant.components import network, onboarding
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_AUTO_DISCOVERY,
    CONF_DEVICE_IP,
    CONF_IPS_TO_REMOVE,
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MANUAL_DEVICES,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_OPTION_MODE,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    OptionMode,
)
from .coordinator import GoveeLocalApiConfig

_LOGGER = logging.getLogger(__name__)


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    adapter = await network.async_get_source_ip(hass, network.PUBLIC_TARGET_IP)

    controller: GoveeController = GoveeController(
        loop=hass.loop,
        logger=_LOGGER,
        listening_address=adapter,
        broadcast_address=CONF_MULTICAST_ADDRESS_DEFAULT,
        broadcast_port=CONF_TARGET_PORT_DEFAULT,
        listening_port=CONF_LISTENING_PORT_DEFAULT,
        discovery_enabled=True,
        discovery_interval=1,
        update_enabled=False,
    )

    try:
        await controller.start()
    except OSError as ex:
        _LOGGER.error("Start failed, errno: %d", ex.errno)
        return False

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not controller.devices:
                await asyncio.sleep(delay=1)
    except TimeoutError:
        _LOGGER.debug("No devices found")

    devices_count = len(controller.devices)
    cleanup_complete: asyncio.Event = controller.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(cleanup_complete.wait(), 1)

    return devices_count > 0


class GoveeConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee light local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)

        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="already_in_progress")

        if user_input is not None:
            if user_input.get(CONF_AUTO_DISCOVERY):
                return await self.async_step_discovery_confirm()
            return self.async_create_entry(title="", data={CONF_AUTO_DISCOVERY: False})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_DISCOVERY,
                        default=True,
                    ): BooleanSelector(),
                }
            ),
        )

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            if not await _async_has_devices(self.hass):
                return self.async_abort(reason="no_devices_found")
            return self.async_create_entry(title="", data={CONF_AUTO_DISCOVERY: True})

        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm", last_step=True)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoveeOptionsFlowHandler:
        """Get the options flow."""
        return GoveeOptionsFlowHandler(config_entry)


class GoveeOptionsFlowHandler(OptionsFlow):
    """Handle a option flow for Govee light local."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        super().__init__()
        self._config_entry = config_entry

        self._options = {
            CONF_MANUAL_DEVICES: set(config_entry.options.get(CONF_MANUAL_DEVICES, [])),
            CONF_AUTO_DISCOVERY: config_entry.options.get(
                CONF_AUTO_DISCOVERY,
                config_entry.data.get(CONF_AUTO_DISCOVERY, True),
            ),
            CONF_IPS_TO_REMOVE: set(config_entry.options.get(CONF_IPS_TO_REMOVE, [])),
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "add_device",
                "remove_device",
                "configure_auto_discovery",
            ],
        )

    async def async_step_configure_auto_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure auto discovery."""
        if user_input is not None:
            self._options[CONF_AUTO_DISCOVERY] = user_input[CONF_AUTO_DISCOVERY]
            return self.async_create_entry(
                title="",
                data={
                    **self._options,
                    CONF_OPTION_MODE: OptionMode.CONFIGURE_AUTO_DISCOVERY,
                },
            )

        config: GoveeLocalApiConfig = GoveeLocalApiConfig.from_config_entry(
            self._config_entry
        )

        return self.async_show_form(
            step_id="configure_auto_discovery",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_DISCOVERY, default=config.auto_discovery
                    ): BooleanSelector(),
                }
            ),
            last_step=True,
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            user_ip = user_input[CONF_DEVICE_IP]
            try:
                IPv4Address(user_ip)
            except AddressValueError:
                return self.async_abort(
                    reason="invalid_ip", description_placeholders={"ip": user_ip}
                )

            self._options.setdefault(CONF_MANUAL_DEVICES, set()).add(user_ip)
            return self.async_create_entry(
                title="",
                data={**self._options, CONF_OPTION_MODE: OptionMode.ADD_DEVICE},
            )

        option_schema = {
            vol.Required(CONF_DEVICE_IP): vol.All(cv.string),
        }

        return self.async_show_form(
            step_id="add_device",
            data_schema=vol.Schema(option_schema),
            last_step=True,
        )

    async def async_step_remove_device(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Remove a device."""
        if user_input is not None:
            self._options[CONF_IPS_TO_REMOVE] = user_input[CONF_IPS_TO_REMOVE]
            return self.async_create_entry(
                title="",
                data={**self._options, CONF_OPTION_MODE: OptionMode.REMOVE_DEVICE},
            )

        coordinator = self.config_entry.runtime_data

        manual_devices = [
            *(
                {"label": f"{device.sku} ({device.ip})", "value": device.ip}
                for device in coordinator.devices
                if device.is_manual
            ),
            *({"label": ip, "value": ip} for ip in coordinator.discovery_queue),
        ]

        if not manual_devices:
            return self.async_abort(reason="no_devices")

        option_schema = {
            vol.Required(CONF_IPS_TO_REMOVE): SelectSelector(
                SelectSelectorConfig(
                    options=manual_devices,
                    custom_value=False,
                    mode=SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
        }

        return self.async_show_form(
            step_id="remove_device",
            data_schema=vol.Schema(option_schema),
            last_step=True,
        )
