"""Config flow for the Home Assistant Connect ZBT-2 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.components import usb
from homeassistant.components.homeassistant_hardware import firmware_config_flow
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
    ResetTarget,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlowContext,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    DEVICE,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_VERSION,
    HARDWARE_NAME,
    MANUFACTURER,
    NABU_CASA_FIRMWARE_RELEASES_URL,
    PID,
    PRODUCT,
    SERIAL_NUMBER,
    VID,
)
from .util import get_usb_service_info

_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:

    class FirmwareInstallFlowProtocol(Protocol):
        """Protocol describing `BaseFirmwareInstallFlow` for a mixin."""

        def _get_translation_placeholders(self) -> dict[str, str]:
            return {}

        async def _install_firmware_step(
            self,
            fw_update_url: str,
            fw_type: str,
            firmware_name: str,
            expected_installed_firmware_type: ApplicationType,
            step_id: str,
            next_step_id: str,
        ) -> ConfigFlowResult: ...

else:
    # Multiple inheritance with `Protocol` seems to break
    FirmwareInstallFlowProtocol = object


class ZBT2FirmwareMixin(ConfigEntryBaseFlow, FirmwareInstallFlowProtocol):
    """Mixin for Home Assistant Connect ZBT-2 firmware methods."""

    context: ConfigFlowContext

    # `rts_dtr` targets older adapters, `baudrate` works for newer ones. The reason we
    # try them in this order is that on older adapters `baudrate` entered the ESP32-S3
    # bootloader instead of the MG24 bootloader.
    BOOTLOADER_RESET_METHODS = [ResetTarget.RTS_DTR, ResetTarget.BAUDRATE]

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        return await self._install_firmware_step(
            fw_update_url=NABU_CASA_FIRMWARE_RELEASES_URL,
            fw_type="zbt2_zigbee_ncp",
            firmware_name="Zigbee",
            expected_installed_firmware_type=ApplicationType.EZSP,
            step_id="install_zigbee_firmware",
            next_step_id="pre_confirm_zigbee",
        )

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self._install_firmware_step(
            fw_update_url=NABU_CASA_FIRMWARE_RELEASES_URL,
            fw_type="zbt2_openthread_rcp",
            firmware_name="OpenThread",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            step_id="install_thread_firmware",
            next_step_id="finish_thread_installation",
        )


class HomeAssistantConnectZBT2ConfigFlow(
    ZBT2FirmwareMixin,
    firmware_config_flow.BaseFirmwareConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Home Assistant Connect ZBT-2."""

    VERSION = 1
    MINOR_VERSION = 1
    ZIGBEE_BAUDRATE = 460800

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the config flow."""
        super().__init__(*args, **kwargs)

        self._usb_info: UsbServiceInfo | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return HomeAssistantConnectZBT2OptionsFlowHandler(config_entry)

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle usb discovery."""
        device = discovery_info.device
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"

        device = discovery_info.device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )

        try:
            await self.async_set_unique_id(unique_id)
        finally:
            self._abort_if_unique_id_configured(updates={DEVICE: device})

        self._usb_info = discovery_info

        # Set parent class attributes
        self._device = self._usb_info.device
        self._hardware_name = HARDWARE_NAME

        return await self.async_step_confirm()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._usb_info is not None
        assert self._probed_firmware_info is not None

        return self.async_create_entry(
            title=HARDWARE_NAME,
            data={
                VID: self._usb_info.vid,
                PID: self._usb_info.pid,
                SERIAL_NUMBER: self._usb_info.serial_number,
                MANUFACTURER: self._usb_info.manufacturer,
                PRODUCT: self._usb_info.description,
                DEVICE: self._usb_info.device,
                FIRMWARE: self._probed_firmware_info.firmware_type.value,
                FIRMWARE_VERSION: self._probed_firmware_info.firmware_version,
            },
        )


class HomeAssistantConnectZBT2OptionsFlowHandler(
    ZBT2FirmwareMixin, firmware_config_flow.BaseFirmwareOptionsFlow
):
    """Zigbee and Thread options flow handlers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._usb_info = get_usb_service_info(self.config_entry)
        self._hardware_name = HARDWARE_NAME
        self._device = self._usb_info.device

        self._probed_firmware_info = FirmwareInfo(
            device=self._device,
            firmware_type=ApplicationType(self.config_entry.data[FIRMWARE]),
            firmware_version=self.config_entry.data[FIRMWARE_VERSION],
            source="guess",
            owners=[],
        )

        # Regenerate the translation placeholders
        self._get_translation_placeholders()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._probed_firmware_info is not None

        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                FIRMWARE: self._probed_firmware_info.firmware_type.value,
                FIRMWARE_VERSION: self._probed_firmware_info.firmware_version,
            },
            options=self.config_entry.options,
        )

        return self.async_create_entry(title="", data={})
