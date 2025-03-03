"""Config flow for Govee light local."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from typing import Any, cast

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
    CONF_LISTENING_PORT_DEFAULT,
    CONF_MULTICAST_ADDRESS_DEFAULT,
    CONF_TARGET_PORT_DEFAULT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)

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
        if user_input is not None:
            if user_input["auto_discovery"]:
                return await self.async_step_govee_discovery()
            return self.async_create_entry(title="", data={"auto_discovery": False})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "auto_discovery",
                        default=True,
                    ): BooleanSelector(),
                }
            ),
        )

    async def async_step_govee_discovery(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup."""
        if user_input is None and onboarding.async_is_onboarded(self.hass):
            self._set_confirm_only()
            return self.async_show_form(step_id="govee_discovery")

        # Get current discovered entries.
        in_progress = self._async_in_progress()

        if not (has_devices := bool(in_progress)):
            discovery_result = _async_has_devices(self.hass)
            if isinstance(discovery_result, bool):
                has_devices = discovery_result
            else:
                has_devices = await cast("asyncio.Future[bool]", discovery_result)

        if not has_devices:
            return self.async_abort(reason="no_devices_found")

        # Cancel the discovered one.
        for flow in in_progress:
            self.hass.config_entries.flow.async_abort(flow["flow_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="", data={"auto_discovery": True})

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
        self._controller = self._config_entry.runtime_data
        self._options = {
            "manual_devices": set(self.config_entry.options["manual_devices"])
            if "manual_devices" in self.config_entry.options
            else set(),
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
            self._options["auto_discovery"] = user_input["auto_discovery"]
            return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="configure_auto_discovery",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "auto_discovery",
                        default=self._config_entry.data.get("auto_discovery", True),
                    ): BooleanSelector(),
                }
            ),
        )

    async def async_step_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            self._options.setdefault("manual_devices", set()).add(
                user_input["device_ip"]
            )
            return self.async_create_entry(title="", data=self._options)

        option_schema = {
            vol.Required("device_ip"): vol.All(cv.string),
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
            self._options.setdefault("ips_to_remove", set()).add(
                user_input["device_ip"]
            )
            return self.async_create_entry(title="", data=self._options)

        coordinator = self.config_entry.runtime_data

        manual_devices = {
            *(device.ip for device in coordinator.devices if device.is_manual),
            *coordinator.discovery_queue,
        }

        option_schema = {
            vol.Required("ips_to_remove"): SelectSelector(
                SelectSelectorConfig(
                    options=list(manual_devices),
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
