"""Config flow for the Home Assistant SkyConnect integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol

from ha_silabs_firmware_client import FirmwareUpdateClient

from homeassistant.components import usb
from homeassistant.components.homeassistant_hardware import (
    firmware_config_flow,
    silabs_multiprotocol_addon,
)
from homeassistant.components.homeassistant_hardware.helpers import (
    async_flash_silabs_firmware,
)
from homeassistant.components.homeassistant_hardware.util import (
    ApplicationType,
    FirmwareInfo,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlowContext,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import (
    DESCRIPTION,
    DEVICE,
    DOCS_WEB_FLASHER_URL,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_VERSION,
    MANUFACTURER,
    NABU_CASA_FIRMWARE_RELEASES_URL,
    PID,
    PRODUCT,
    SERIAL_NUMBER,
    VID,
    HardwareVariant,
)
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


class SkyConnectTranslationMixin(ConfigEntryBaseFlow, TranslationPlaceholderProtocol):
    """Translation placeholder mixin for Home Assistant SkyConnect."""

    context: ConfigFlowContext

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
    MINOR_VERSION = 4

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the config flow."""
        super().__init__(*args, **kwargs)

        self._usb_info: UsbServiceInfo | None = None
        self._hw_variant: HardwareVariant | None = None
        self._firmware_install_task: asyncio.Task | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        firmware_type = ApplicationType(config_entry.data[FIRMWARE])

        if firmware_type is ApplicationType.CPC:
            return HomeAssistantSkyConnectMultiPanOptionsFlowHandler(config_entry)

        return HomeAssistantSkyConnectOptionsFlowHandler(config_entry)

    async def async_step_usb(self, discovery_info: UsbServiceInfo) -> ConfigFlowResult:
        """Handle usb discovery."""
        device = discovery_info.device
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"

        if await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(updates={DEVICE: device})

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

    async def _install_firmware_step(
        self,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        next_step_id: str,
    ) -> ConfigFlowResult:
        assert self._device is not None

        if not self._firmware_install_task:
            session = async_get_clientsession(self.hass)
            client = FirmwareUpdateClient(NABU_CASA_FIRMWARE_RELEASES_URL, session)
            manifest = await client.async_update_data()

            fw_meta = next(
                fw for fw in manifest.firmwares if fw.filename.startswith(fw_type)
            )

            fw_data = await client.async_fetch_firmware(fw_meta)
            self._firmware_install_task = self.hass.async_create_task(
                async_flash_silabs_firmware(
                    hass=self.hass,
                    device=self._device,
                    fw_data=fw_data,
                    expected_installed_firmware_type=expected_installed_firmware_type,
                    bootloader_reset_type=None,
                    progress_callback=lambda offset, total: self.async_update_progress(
                        offset / total
                    ),
                ),
                f"Flash {firmware_name} firmware",
            )

        if not self._firmware_install_task.done():
            return self.async_show_progress(
                progress_action="install_firmware",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "firmware_name": firmware_name,
                },
                progress_task=self._firmware_install_task,
            )

        return self.async_show_progress_done(next_step_id=next_step_id)

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        return await self._install_firmware_step(
            fw_type="zigbee_ncp",
            firmware_name="Zigbee",
            expected_installed_firmware_type=ApplicationType.EZSP,
            next_step_id="confirm_zigbee",
        )

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        return await self._install_firmware_step(
            fw_type="openthread_rcp",
            firmware_name="OpenThread",
            expected_installed_firmware_type=ApplicationType.SPINEL,
            next_step_id="start_otbr_addon",
        )

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._usb_info is not None
        assert self._hw_variant is not None
        assert self._probed_firmware_info is not None

        return self.async_create_entry(
            title=self._hw_variant.full_name,
            data={
                VID: self._usb_info.vid,
                PID: self._usb_info.pid,
                SERIAL_NUMBER: self._usb_info.serial_number,
                MANUFACTURER: self._usb_info.manufacturer,
                DESCRIPTION: self._usb_info.description,  # For backwards compatibility
                PRODUCT: self._usb_info.description,
                DEVICE: self._usb_info.device,
                FIRMWARE: self._probed_firmware_info.firmware_type.value,
                FIRMWARE_VERSION: self._probed_firmware_info.firmware_version,
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
        return silabs_multiprotocol_addon.SerialPortSettings(
            device=self.config_entry.data[DEVICE],
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
                FIRMWARE: ApplicationType.EZSP.value,
                FIRMWARE_VERSION: None,
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
            self.config_entry.data[PRODUCT]
        )
        self._hardware_name = self._hw_variant.full_name
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
