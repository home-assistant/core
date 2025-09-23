"""Config flow for the Home Assistant SkyConnect integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from enum import StrEnum
import logging
from typing import Any

from aiohttp import ClientError
from ha_silabs_firmware_client import FirmwareUpdateClient, ManifestMissing
from universal_silabs_flasher.common import Version
from universal_silabs_flasher.firmware import NabuCasaMetadata

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlow,
    ConfigFlowResult,
    FlowType,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, progress_step
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.hassio import is_hassio

from .const import OTBR_DOMAIN, ZHA_DOMAIN
from .util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
    async_flash_silabs_firmware,
    get_otbr_addon_manager,
    guess_firmware_info,
    guess_hardware_owners,
    probe_silabs_firmware_info,
)

_LOGGER = logging.getLogger(__name__)

STEP_PICK_FIRMWARE_THREAD = "pick_firmware_thread"
STEP_PICK_FIRMWARE_ZIGBEE = "pick_firmware_zigbee"
STEP_PICK_FIRMWARE_THREAD_MIGRATE = "pick_firmware_thread_migrate"
STEP_PICK_FIRMWARE_ZIGBEE_MIGRATE = "pick_firmware_zigbee_migrate"


class PickedFirmwareType(StrEnum):
    """Firmware types that can be picked."""

    THREAD = "thread"
    ZIGBEE = "zigbee"


class ZigbeeIntegration(StrEnum):
    """Zigbee integrations that can be picked."""

    OTHER = "other"
    ZHA = "zha"


class BaseFirmwareInstallFlow(ConfigEntryBaseFlow, ABC):
    """Base flow to install firmware."""

    ZIGBEE_BAUDRATE = 115200  # Default, subclasses may override
    _picked_firmware_type: PickedFirmwareType

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate base flow."""
        super().__init__(*args, **kwargs)

        self._probed_firmware_info: FirmwareInfo | None = None
        self._device: str | None = None  # To be set in a subclass
        self._hardware_name: str = "unknown"  # To be set in a subclass
        self._zigbee_integration = ZigbeeIntegration.ZHA

        self.addon_uninstall_task: asyncio.Task | None = None
        self.firmware_install_task: asyncio.Task | None = None
        self.installing_firmware_name: str | None = None

    def _get_translation_placeholders(self) -> dict[str, str]:
        """Shared translation placeholders."""
        placeholders = {
            "firmware_type": (
                self._probed_firmware_info.firmware_type.value
                if self._probed_firmware_info is not None
                else "unknown"
            ),
            "model": self._hardware_name,
        }

        self.context["title_placeholders"] = placeholders

        return placeholders

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return add-on info."""
        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": addon_manager.addon_name,
                },
            ) from err

        return addon_info

    async def async_step_pick_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread or Zigbee firmware."""
        # Determine if ZHA or Thread are already configured to present migrate options
        zha_entries = self.hass.config_entries.async_entries(ZHA_DOMAIN)
        otbr_entries = self.hass.config_entries.async_entries(OTBR_DOMAIN)

        return self.async_show_menu(
            step_id="pick_firmware",
            menu_options=[
                (
                    STEP_PICK_FIRMWARE_ZIGBEE_MIGRATE
                    if zha_entries
                    else STEP_PICK_FIRMWARE_ZIGBEE
                ),
                (
                    STEP_PICK_FIRMWARE_THREAD_MIGRATE
                    if otbr_entries
                    else STEP_PICK_FIRMWARE_THREAD
                ),
            ],
            description_placeholders=self._get_translation_placeholders(),
        )

    async def _probe_firmware_info(
        self,
        probe_methods: tuple[ApplicationType, ...] = (
            # We probe in order of frequency: Zigbee, Thread, then multi-PAN
            ApplicationType.GECKO_BOOTLOADER,
            ApplicationType.EZSP,
            ApplicationType.SPINEL,
            ApplicationType.CPC,
        ),
    ) -> bool:
        """Probe the firmware currently on the device."""
        assert self._device is not None

        self._probed_firmware_info = await probe_silabs_firmware_info(
            self._device,
            probe_methods=probe_methods,
        )

        return (
            self._probed_firmware_info is not None
            and self._probed_firmware_info.firmware_type
            in (
                ApplicationType.EZSP,
                ApplicationType.SPINEL,
                ApplicationType.CPC,
            )
        )

    async def _install_firmware_step(
        self,
        fw_update_url: str,
        fw_type: str,
        firmware_name: str,
        expected_installed_firmware_type: ApplicationType,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        assert self._device is not None

        if not self.firmware_install_task:
            # Keep track of the firmware we're working with, for error messages
            self.installing_firmware_name = firmware_name

            # Installing new firmware is only truly required if the wrong type is
            # installed: upgrading to the latest release of the current firmware type
            # isn't strictly necessary for functionality.
            firmware_install_required = self._probed_firmware_info is None or (
                self._probed_firmware_info.firmware_type
                != expected_installed_firmware_type
            )

            session = async_get_clientsession(self.hass)
            client = FirmwareUpdateClient(fw_update_url, session)

            try:
                manifest = await client.async_update_data()
                fw_manifest = next(
                    fw for fw in manifest.firmwares if fw.filename.startswith(fw_type)
                )
            except (StopIteration, TimeoutError, ClientError, ManifestMissing):
                _LOGGER.warning(
                    "Failed to fetch firmware update manifest", exc_info=True
                )

                # Not having internet access should not prevent setup
                if not firmware_install_required:
                    _LOGGER.debug(
                        "Skipping firmware upgrade due to index download failure"
                    )
                    return self.async_show_progress_done(next_step_id=next_step_id)

                return self.async_show_progress_done(
                    next_step_id="firmware_download_failed"
                )

            if not firmware_install_required:
                assert self._probed_firmware_info is not None

                # Make sure we do not downgrade the firmware
                fw_metadata = NabuCasaMetadata.from_json(fw_manifest.metadata)
                fw_version = fw_metadata.get_public_version()
                probed_fw_version = Version(self._probed_firmware_info.firmware_version)

                if probed_fw_version >= fw_version:
                    _LOGGER.debug(
                        "Not downgrading firmware, installed %s is newer than available %s",
                        probed_fw_version,
                        fw_version,
                    )
                    return self.async_show_progress_done(next_step_id=next_step_id)

            try:
                fw_data = await client.async_fetch_firmware(fw_manifest)
            except (TimeoutError, ClientError, ValueError):
                _LOGGER.warning("Failed to fetch firmware update", exc_info=True)

                # If we cannot download new firmware, we shouldn't block setup
                if not firmware_install_required:
                    _LOGGER.debug(
                        "Skipping firmware upgrade due to image download failure"
                    )
                    return self.async_show_progress_done(next_step_id=next_step_id)

                # Otherwise, fail
                return self.async_show_progress_done(
                    next_step_id="firmware_download_failed"
                )

            self.firmware_install_task = self.hass.async_create_task(
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

        if not self.firmware_install_task.done():
            return self.async_show_progress(
                step_id=step_id,
                progress_action="install_firmware",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "firmware_name": firmware_name,
                },
                progress_task=self.firmware_install_task,
            )

        try:
            await self.firmware_install_task
        except HomeAssistantError:
            _LOGGER.exception("Failed to flash firmware")
            return self.async_show_progress_done(next_step_id="firmware_install_failed")

        return self.async_show_progress_done(next_step_id=next_step_id)

    async def _configure_and_start_otbr_addon(self) -> None:
        """Configure and start the OTBR addon."""

        # Before we start the addon, confirm that the correct firmware is running
        # and populate `self._probed_firmware_info` with the correct information
        if not await self._probe_firmware_info(probe_methods=(ApplicationType.SPINEL,)):
            raise AbortFlow(
                "unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        assert self._device is not None
        new_addon_config = {
            **addon_info.options,
            "device": self._device,
            "baudrate": 460800,
            "flow_control": True,
            "autoflash_firmware": False,
        }

        _LOGGER.debug("Reconfiguring OTBR addon with %s", new_addon_config)

        try:
            await otbr_manager.async_set_addon_options(new_addon_config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_set_config_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": otbr_manager.addon_name,
                },
            ) from err

        await otbr_manager.async_start_addon_waiting()

    async def async_step_firmware_download_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when firmware download failed."""
        assert self.installing_firmware_name is not None
        return self.async_abort(
            reason="fw_download_failed",
            description_placeholders={
                **self._get_translation_placeholders(),
                "firmware_name": self.installing_firmware_name,
            },
        )

    async def async_step_firmware_install_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when firmware install failed."""
        assert self.installing_firmware_name is not None
        return self.async_abort(
            reason="fw_install_failed",
            description_placeholders={
                **self._get_translation_placeholders(),
                "firmware_name": self.installing_firmware_name,
            },
        )

    async def async_step_zigbee_installation_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the installation type step."""
        return self.async_show_menu(
            step_id="zigbee_installation_type",
            menu_options=[
                "zigbee_intent_recommended",
                "zigbee_intent_custom",
            ],
        )

    async def async_step_zigbee_intent_recommended(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select recommended installation type."""
        self._zigbee_integration = ZigbeeIntegration.ZHA
        return await self._async_continue_picked_firmware()

    async def async_step_zigbee_intent_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select custom installation type."""
        return await self.async_step_zigbee_integration()

    async def async_step_zigbee_integration(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Zigbee integration."""
        return self.async_show_menu(
            step_id="zigbee_integration",
            menu_options=[
                "zigbee_integration_zha",
                "zigbee_integration_other",
            ],
        )

    async def async_step_zigbee_integration_zha(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select ZHA integration."""
        self._zigbee_integration = ZigbeeIntegration.ZHA
        return await self._async_continue_picked_firmware()

    async def async_step_zigbee_integration_other(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select other Zigbee integration."""
        self._zigbee_integration = ZigbeeIntegration.OTHER
        return await self._async_continue_picked_firmware()

    async def _async_continue_picked_firmware(self) -> ConfigFlowResult:
        """Continue to the picked firmware step."""
        if not await self._probe_firmware_info():
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        if self._picked_firmware_type == PickedFirmwareType.ZIGBEE:
            return await self.async_step_install_zigbee_firmware()

        return await self.async_step_prepare_thread_installation()

    async def async_step_prepare_thread_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare for Thread installation by stopping the OTBR addon if needed."""
        if not is_hassio(self.hass):
            return self.async_abort(
                reason="not_hassio_thread",
                description_placeholders=self._get_translation_placeholders(),
            )

        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        if addon_info.state == AddonState.RUNNING:
            # Stop the addon before continuing to flash firmware
            await otbr_manager.async_stop_addon()

        return await self.async_step_install_thread_firmware()

    async def async_step_finish_thread_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish Thread installation by starting the OTBR addon."""
        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_otbr_addon()

        return await self.async_step_start_otbr_addon()

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        self._picked_firmware_type = PickedFirmwareType.ZIGBEE
        return await self.async_step_zigbee_installation_type()

    async def async_step_pick_firmware_zigbee_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware. Migration is automatic."""
        return await self.async_step_pick_firmware_zigbee()

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        raise NotImplementedError

    async def async_step_pre_confirm_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pre-confirm Zigbee setup."""

        # This step is necessary to prevent `user_input` from being passed through
        return await self.async_step_continue_zigbee()

    async def async_step_continue_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Continue Zigbee setup."""
        assert self._device is not None
        assert self._hardware_name is not None

        if not await self._probe_firmware_info(probe_methods=(ApplicationType.EZSP,)):
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        if self._zigbee_integration == ZigbeeIntegration.OTHER:
            return self._async_flow_finished()

        result = await self.hass.config_entries.flow.async_init(
            ZHA_DOMAIN,
            context={"source": "hardware"},
            data={
                "name": self._hardware_name,
                "port": {
                    "path": self._device,
                    "baudrate": self.ZIGBEE_BAUDRATE,
                    "flow_control": "hardware",
                },
                "radio_type": "ezsp",
            },
        )
        return self._continue_zha_flow(result)

    @callback
    def _continue_zha_flow(self, zha_result: ConfigFlowResult) -> ConfigFlowResult:
        """Continue the ZHA flow."""
        raise NotImplementedError

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware."""
        self._picked_firmware_type = PickedFirmwareType.THREAD
        return await self._async_continue_picked_firmware()

    async def async_step_pick_firmware_thread_migrate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware. Migration is automatic."""
        return await self.async_step_pick_firmware_thread()

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        raise NotImplementedError

    @progress_step(
        description_placeholders=lambda self: {
            **self._get_translation_placeholders(),
            "addon_name": get_otbr_addon_manager(self.hass).addon_name,
        }
    )
    async def async_step_install_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress dialog for installing the OTBR addon."""
        addon_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        _LOGGER.debug("OTBR addon info: %s", addon_info)

        try:
            await addon_manager.async_install_addon_waiting()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_install_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": addon_manager.addon_name,
                },
            ) from err

        return await self.async_step_finish_thread_installation()

    @progress_step(
        description_placeholders=lambda self: {
            **self._get_translation_placeholders(),
            "addon_name": get_otbr_addon_manager(self.hass).addon_name,
        }
    )
    async def async_step_start_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure OTBR to point to the SkyConnect and run the addon."""
        try:
            await self._configure_and_start_otbr_addon()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_start_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": get_otbr_addon_manager(self.hass).addon_name,
                },
            ) from err

        return await self.async_step_pre_confirm_otbr()

    async def async_step_pre_confirm_otbr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pre-confirm OTBR setup."""

        # This step is necessary to prevent `user_input` from being passed through
        return await self.async_step_confirm_otbr()

    async def async_step_confirm_otbr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm OTBR setup."""
        assert self._device is not None

        if user_input is None:
            return self.async_show_form(
                step_id="confirm_otbr",
                description_placeholders=self._get_translation_placeholders(),
            )

        # OTBR discovery is done automatically via hassio
        return self._async_flow_finished()

    @abstractmethod
    def _async_flow_finished(self) -> ConfigFlowResult:
        """Finish the flow."""
        raise NotImplementedError


class BaseFirmwareConfigFlow(BaseFirmwareInstallFlow, ConfigFlow):
    """Base config flow for installing firmware."""

    @staticmethod
    @callback
    @abstractmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        raise NotImplementedError

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovery."""
        assert self._device is not None
        fw_info = await guess_firmware_info(self.hass, self._device)

        # If our guess for the firmware type is actually running, we can save the user
        # an unnecessary confirmation and silently confirm the flow
        for owner in fw_info.owners:
            if await owner.is_running(self.hass):
                self._probed_firmware_info = fw_info
                return self._async_flow_finished()

        return await self.async_step_pick_firmware()

    @callback
    def _continue_zha_flow(self, zha_result: ConfigFlowResult) -> ConfigFlowResult:
        """Continue the ZHA flow."""
        next_flow_id = zha_result["flow_id"]

        result = self._async_flow_finished()
        return (
            self.async_create_entry(
                title=result["title"] or self._hardware_name,
                data=result["data"],
                next_flow=(FlowType.CONFIG_FLOW, next_flow_id),
            )
            | result  # update all items with the child result
        )


class BaseFirmwareOptionsFlow(BaseFirmwareInstallFlow, OptionsFlow):
    """Zigbee and Thread options flow handlers."""

    _probed_firmware_info: FirmwareInfo

    def __init__(self, config_entry: ConfigEntry, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._config_entry = config_entry

        # Make `context` a regular dictionary
        self.context = {}

        # Subclasses are expected to override `_device` and `_hardware_name`

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow."""
        return await self.async_step_pick_firmware()

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        assert self._device is not None
        owners = await guess_hardware_owners(self.hass, self._device)

        for info in owners:
            for owner in info.owners:
                if info.source == OTBR_DOMAIN and isinstance(owner, OwningAddon):
                    raise AbortFlow(
                        "otbr_still_using_stick",
                        description_placeholders=self._get_translation_placeholders(),
                    )

        return await super().async_step_pick_firmware_zigbee(user_input)

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware."""
        assert self._device is not None

        owners = await guess_hardware_owners(self.hass, self._device)

        for info in owners:
            for owner in info.owners:
                if info.source == ZHA_DOMAIN and isinstance(owner, OwningIntegration):
                    raise AbortFlow(
                        "zha_still_using_stick",
                        description_placeholders=self._get_translation_placeholders(),
                    )

        return await super().async_step_pick_firmware_thread(user_input)

    @callback
    def _continue_zha_flow(self, zha_result: ConfigFlowResult) -> ConfigFlowResult:
        """Continue the ZHA flow."""
        # The options flow cannot return a next_flow yet, so we just finish here.
        # The options flow should be changed to a reconfigure flow.
        return self._async_flow_finished()
