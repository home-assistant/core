"""Config flow for the Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.homeassistant_hardware import (
    firmware_config_flow,
    silabs_multiprotocol_addon,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import DOCS_WEB_FLASHER_URL, DOMAIN, HardwareVariant
from .util import get_hardware_variant, get_usb_service_info

_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:

    class TranslationPlaceholderProtocol(Protocol):
        """Protocol describing `BaseFirmwareInstallFlow`'s translation placeholders."""

        def _get_translation_placeholders(self) -> dict[str, str]:
            return {}
else:
    # Multiple inheritance with `Protocol` seems to break
    TranslationPlaceholderProtocol = object


class SkyConnectTranslationMixin(TranslationPlaceholderProtocol):
    """Translation placeholder mixin for Home Assistant SkyConnect."""

    context: dict[str, Any]

    def _get_translation_placeholders(self) -> dict[str, str]:
        """Shared translation placeholders."""
        placeholders = {
            **super()._get_translation_placeholders(),
            "docs_web_flasher_url": DOCS_WEB_FLASHER_URL,
        }

        self.context["title_placeholders"] = placeholders

        return placeholders


class HomeAssistantSkyConnectConfigFlow(
    SkyConnectTranslationMixin,
    firmware_config_flow.BaseFirmwareConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Home Assistant SkyConnect."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the config flow."""
        super().__init__(*args, **kwargs)

        self._usb_info: usb.UsbServiceInfo | None = None
        self._hw_variant: HardwareVariant | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        firmware_type = ApplicationType(config_entry.data["firmware"])

        if firmware_type is ApplicationType.CPC:
            return HomeAssistantSkyConnectMultiPanOptionsFlowHandler(config_entry)

        return HomeAssistantSkyConnectOptionsFlowHandler(config_entry)

    async def async_step_usb(
        self, discovery_info: usb.UsbServiceInfo
    ) -> ConfigFlowResult:
        """Handle usb discovery."""
        device = discovery_info.device
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"

        if await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(updates={"device": device})

        discovery_info.device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )

        self._usb_info = discovery_info

        assert description is not None
        self._hw_variant = HardwareVariant.from_usb_product_name(description)

        # Set parent class attributes
        self._device = self._usb_info.device
        self._hardware_name = self._hw_variant.full_name

        return await self.async_step_confirm()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._usb_info is not None
        assert self._hw_variant is not None
        assert self._probed_firmware_type is not None

        return self.async_create_entry(
            title=self._hw_variant.full_name,
            data={
                "vid": self._usb_info.vid,
                "pid": self._usb_info.pid,
                "serial_number": self._usb_info.serial_number,
                "manufacturer": self._usb_info.manufacturer,
                "description": self._usb_info.description,  # For backwards compatibility
                "product": self._usb_info.description,
                "device": self._usb_info.device,
                "firmware": self._probed_firmware_type.value,
            },
        )


class HomeAssistantSkyConnectMultiPanOptionsFlowHandler(
    silabs_multiprotocol_addon.OptionsFlowHandler
):
    """Multi-PAN options flow for Home Assistant SkyConnect."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        usb_dev = self.config_entry.data["device"]
        # The call to get_serial_by_id can be removed in HA Core 2024.1
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, usb_dev)
        return silabs_multiprotocol_addon.SerialPortSettings(
            device=dev_path,
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {"usb": get_usb_service_info(self.config_entry)}

    @property
    def _hw_variant(self) -> HardwareVariant:
        """Return the hardware variant."""
        return get_hardware_variant(self.config_entry)

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return f"{self._hw_variant.short_name} Multiprotocol"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return self._hw_variant.full_name

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish flashing and update the config entry."""
        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                "firmware": ApplicationType.EZSP.value,
            },
            options=self.config_entry.options,
        )

        return await super().async_step_flashing_complete(user_input)


class HomeAssistantSkyConnectOptionsFlowHandler(
    SkyConnectTranslationMixin, firmware_config_flow.BaseFirmwareOptionsFlow
):
    """Zigbee and Thread options flow handlers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._usb_info = get_usb_service_info(self.config_entry)
        self._hw_variant = HardwareVariant.from_usb_product_name(
            self.config_entry.data["product"]
        )
        self._hardware_name = self._hw_variant.full_name
        self._device = self._usb_info.device

        # Regenerate the translation placeholders
        self._get_translation_placeholders()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._probed_firmware_type is not None

        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                "firmware": self._probed_firmware_type.value,
            },
            options=self.config_entry.options,
        )

        return self.async_create_entry(title="", data={})
