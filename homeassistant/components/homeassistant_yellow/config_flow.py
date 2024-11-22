"""Config flow for the Home Assistant Yellow integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any, final

import aiohttp
from universal_silabs_flasher.const import ApplicationType
import voluptuous as vol

from homeassistant.components.hassio import (
    HassioAPIError,
    async_get_yellow_settings,
    async_reboot_host,
    async_set_yellow_settings,
)
from homeassistant.components.homeassistant_hardware.firmware_config_flow import (
    BaseFirmwareConfigFlow,
    BaseFirmwareOptionsFlow,
)
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    OptionsFlowHandler as MultiprotocolOptionsFlowHandler,
    SerialPortSettings as MultiprotocolSerialPortSettings,
)
from homeassistant.config_entries import (
    SOURCE_HARDWARE,
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import discovery_flow, selector

from .const import DOMAIN, FIRMWARE, RADIO_DEVICE, ZHA_DOMAIN, ZHA_HW_DISCOVERY_DATA
from .hardware import BOARD_NAME

_LOGGER = logging.getLogger(__name__)

STEP_HW_SETTINGS_SCHEMA = vol.Schema(
    {
        vol.Required("disk_led"): selector.BooleanSelector(),
        vol.Required("heartbeat_led"): selector.BooleanSelector(),
        vol.Required("power_led"): selector.BooleanSelector(),
    }
)


class HomeAssistantYellowConfigFlow(BaseFirmwareConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant Yellow."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate config flow."""
        super().__init__(*args, **kwargs)

        self._device = RADIO_DEVICE

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        firmware_type = ApplicationType(config_entry.data[FIRMWARE])

        if firmware_type is ApplicationType.CPC:
            return HomeAssistantYellowMultiPanOptionsFlowHandler(config_entry)

        return HomeAssistantYellowOptionsFlowHandler(config_entry)

    async def async_step_system(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # We do not actually use any portion of `BaseFirmwareConfigFlow` beyond this
        await self._probe_firmware_type()

        # Kick off ZHA hardware discovery automatically if Zigbee firmware is running
        if self._probed_firmware_type is ApplicationType.EZSP:
            discovery_flow.async_create_flow(
                self.hass,
                ZHA_DOMAIN,
                context={"source": SOURCE_HARDWARE},
                data=ZHA_HW_DISCOVERY_DATA,
            )

        return self._async_flow_finished()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        return self.async_create_entry(
            title=BOARD_NAME,
            data={
                # Assume the firmware type is EZSP if we cannot probe it
                FIRMWARE: (self._probed_firmware_type or ApplicationType.EZSP).value,
            },
        )


class BaseHomeAssistantYellowOptionsFlow(OptionsFlow, ABC):
    """Base Home Assistant Yellow options flow shared between firmware and multi-PAN."""

    _hw_settings: dict[str, bool] | None = None

    @abstractmethod
    async def async_step_main_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the main menu."""

    @final
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow."""
        return await self.async_step_main_menu()

    @final
    async def async_step_on_supervisor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle logic when on Supervisor host."""
        return await self.async_step_main_menu()

    async def async_step_hardware_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle hardware settings."""

        if user_input is not None:
            if self._hw_settings == user_input:
                return self.async_create_entry(data={})
            try:
                async with asyncio.timeout(10):
                    await async_set_yellow_settings(self.hass, user_input)
            except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
                _LOGGER.warning("Failed to write hardware settings", exc_info=err)
                return self.async_abort(reason="write_hw_settings_error")
            return await self.async_step_reboot_menu()

        try:
            async with asyncio.timeout(10):
                self._hw_settings: dict[str, bool] = await async_get_yellow_settings(
                    self.hass
                )
        except (aiohttp.ClientError, TimeoutError, HassioAPIError) as err:
            _LOGGER.warning("Failed to read hardware settings", exc_info=err)
            return self.async_abort(reason="read_hw_settings_error")

        schema = self.add_suggested_values_to_schema(
            STEP_HW_SETTINGS_SCHEMA, self._hw_settings
        )

        return self.async_show_form(step_id="hardware_settings", data_schema=schema)

    async def async_step_reboot_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reboot host."""
        return self.async_show_menu(
            step_id="reboot_menu",
            menu_options=[
                "reboot_now",
                "reboot_later",
            ],
        )

    async def async_step_reboot_now(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reboot now."""
        await async_reboot_host(self.hass)
        return self.async_create_entry(data={})

    async def async_step_reboot_later(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reboot later."""
        return self.async_create_entry(data={})


class HomeAssistantYellowMultiPanOptionsFlowHandler(
    BaseHomeAssistantYellowOptionsFlow, MultiprotocolOptionsFlowHandler
):
    """Handle a multi-PAN options flow for Home Assistant Yellow."""

    async def async_step_main_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the main menu."""
        return self.async_show_menu(
            step_id="main_menu",
            menu_options=[
                "hardware_settings",
                "multipan_settings",
            ],
        )

    async def async_step_multipan_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle multipan settings."""
        return await MultiprotocolOptionsFlowHandler.async_step_on_supervisor(
            self, user_input
        )

    async def _async_serial_port_settings(
        self,
    ) -> MultiprotocolSerialPortSettings:
        """Return the radio serial port settings."""
        return MultiprotocolSerialPortSettings(
            device=RADIO_DEVICE,
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {"hw": ZHA_HW_DISCOVERY_DATA}

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "Yellow Multiprotocol"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return BOARD_NAME

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish flashing and update the config entry."""
        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                FIRMWARE: ApplicationType.EZSP.value,
            },
        )

        return await super().async_step_flashing_complete(user_input)


class HomeAssistantYellowOptionsFlowHandler(
    BaseHomeAssistantYellowOptionsFlow, BaseFirmwareOptionsFlow
):
    """Handle a firmware options flow for Home Assistant Yellow."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._hardware_name = BOARD_NAME
        self._device = RADIO_DEVICE

        # Regenerate the translation placeholders
        self._get_translation_placeholders()

    async def async_step_main_menu(self, _: None = None) -> ConfigFlowResult:
        """Show the main menu."""
        return self.async_show_menu(
            step_id="main_menu",
            menu_options=[
                "hardware_settings",
                "firmware_settings",
            ],
        )

    async def async_step_firmware_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle firmware configuration settings."""
        return await super().async_step_pick_firmware()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._probed_firmware_type is not None

        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                FIRMWARE: self._probed_firmware_type.value,
            },
        )

        return self.async_create_entry(title="", data={})
