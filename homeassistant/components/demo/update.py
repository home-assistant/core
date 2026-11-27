"""Demo platform that offers fake update entities."""

import asyncio
from typing import Any, override

from homeassistant.components.update import (
    MANUAL_ACTION_CONFIRM_ON_DEVICE,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
    UpdateInstallPhase,
    UpdateManualAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

FAKE_INSTALL_SLEEP_TIME = 0.5
# Long enough to see the manual action in the frontend
FAKE_WAITING_FOR_USER_STEPS = 20


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up demo update platform."""
    async_add_entities(
        [
            DemoUpdate(
                unique_id="update_no_install",
                device_name="Demo Update No Install",
                title="Awesomesoft Inc.",
                installed_version="1.0.0",
                latest_version="1.0.1",
                release_summary="Awesome update, fixing everything!",
                release_url="https://www.example.com/release/1.0.1",
                support_install=False,
            ),
            DemoUpdate(
                unique_id="update_2_date",
                device_name="Demo No Update",
                title="AdGuard Home",
                installed_version="1.0.0",
                latest_version="1.0.0",
            ),
            DemoUpdate(
                unique_id="update_addon",
                device_name="Demo add-on",
                title="AdGuard Home",
                installed_version="1.0.0",
                latest_version="1.0.1",
                release_summary="Awesome update, fixing everything!",
                release_url="https://www.example.com/release/1.0.1",
            ),
            DemoUpdate(
                unique_id="update_light_bulb",
                device_name="Demo Living Room Bulb Update",
                title="Philips Lamps Firmware",
                installed_version="1.93.3",
                latest_version="1.94.2",
                release_summary="Added support for effects",
                release_url="https://www.example.com/release/1.93.3",
                device_class=UpdateDeviceClass.FIRMWARE,
            ),
            DemoUpdate(
                unique_id="update_support_progress",
                device_name="Demo Update with Progress",
                title="Philips Lamps Firmware",
                installed_version="1.93.3",
                latest_version="1.94.2",
                support_progress=True,
                release_summary="Added support for effects",
                support_release_notes=True,
                release_url="https://www.example.com/release/1.93.3",
                device_class=UpdateDeviceClass.FIRMWARE,
                update_steps=10,
            ),
            DemoUpdate(
                unique_id="update_support_decimal_progress",
                device_name="Demo Update with Decimal Progress",
                title="Philips Lamps Firmware",
                installed_version="1.93.3",
                latest_version="1.94.2",
                support_progress=True,
                release_summary="Added support for effects",
                support_release_notes=True,
                release_url="https://www.example.com/release/1.93.3",
                device_class=UpdateDeviceClass.FIRMWARE,
                display_precision=2,
                update_steps=1000,
            ),
            DemoUpdate(
                unique_id="update_install_phases",
                device_name="Demo Update with Install Phases",
                title="Awesomesoft Inc.",
                installed_version="1.0.0",
                latest_version="1.1.0",
                support_progress=True,
                update_steps=10,
                install_phases=(
                    UpdateInstallPhase.PREPARING,
                    UpdateInstallPhase.BACKING_UP,
                    UpdateInstallPhase.WAITING,
                    UpdateInstallPhase.DOWNLOADING,
                    UpdateInstallPhase.INSTALLING,
                    UpdateInstallPhase.RESTARTING,
                    UpdateInstallPhase.FINISHING,
                ),
            ),
            DemoUpdate(
                unique_id="update_manual_action",
                device_name="Demo Update with Manual Action",
                title="Awesomesoft Inc.",
                installed_version="1.0.0",
                latest_version="1.1.0",
                support_progress=True,
                update_steps=10,
                install_phases=(
                    UpdateInstallPhase.PREPARING,
                    UpdateInstallPhase.BACKING_UP,
                    UpdateInstallPhase.WAITING,
                    UpdateInstallPhase.DOWNLOADING,
                    UpdateInstallPhase.WAITING_FOR_USER,
                    UpdateInstallPhase.INSTALLING,
                    UpdateInstallPhase.RESTARTING,
                    UpdateInstallPhase.FINISHING,
                ),
                manual_action=MANUAL_ACTION_CONFIRM_ON_DEVICE,
            ),
            DemoUpdate(
                unique_id="update_power_cycle",
                device_name="Demo Hallway Bulb",
                title="Philips Lamps Firmware",
                installed_version="1.94.2",
                latest_version="1.95.0",
                support_progress=True,
                device_class=UpdateDeviceClass.FIRMWARE,
                update_steps=10,
                install_phases=(
                    UpdateInstallPhase.DOWNLOADING,
                    UpdateInstallPhase.INSTALLING,
                    UpdateInstallPhase.WAITING_FOR_USER,
                    UpdateInstallPhase.FINISHING,
                ),
                manual_action=UpdateManualAction(
                    translation_domain=DOMAIN,
                    translation_key="power_cycle",
                    translation_placeholders={"device_name": "Demo Hallway Bulb"},
                ),
            ),
        ]
    )


async def _fake_install(steps: int = 1) -> None:
    """Fake install an update."""
    await asyncio.sleep(FAKE_INSTALL_SLEEP_TIME * steps)


class DemoUpdate(UpdateEntity):
    """Representation of a demo update entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(
        self,
        *,
        unique_id: str,
        device_name: str,
        title: str | None,
        installed_version: str | None,
        latest_version: str | None,
        release_summary: str | None = None,
        release_url: str | None = None,
        support_progress: bool = False,
        support_install: bool = True,
        support_release_notes: bool = False,
        device_class: UpdateDeviceClass | None = None,
        display_precision: int = 0,
        update_steps: int = 100,
        install_phases: tuple[UpdateInstallPhase, ...] = (),
        manual_action: UpdateManualAction | None = None,
    ) -> None:
        """Initialize the Demo select entity."""
        self._attr_installed_version = installed_version
        self._attr_device_class = device_class
        self._attr_display_precision = display_precision
        self._attr_latest_version = latest_version
        self._attr_release_summary = release_summary
        self._attr_release_url = release_url
        self._attr_title = title
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_manual_action = manual_action
        self._update_steps = update_steps
        self._install_phases = install_phases
        if support_install:
            self._attr_supported_features |= (
                UpdateEntityFeature.INSTALL
                | UpdateEntityFeature.BACKUP
                | UpdateEntityFeature.SPECIFIC_VERSION
            )
        if support_progress:
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

        if support_release_notes:
            self._attr_supported_features |= UpdateEntityFeature.RELEASE_NOTES

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if self._install_phases:
            await self._async_install_in_phases(backup)
        elif self.supported_features & UpdateEntityFeature.PROGRESS:
            self._attr_in_progress = True
            for progress in range(0, self._update_steps, 1):
                self._attr_update_percentage = progress / (self._update_steps / 100)
                self.async_write_ha_state()
                await _fake_install()

        self._attr_in_progress = False
        self._attr_update_percentage = None
        self._attr_installed_version = (
            version if version is not None else self.latest_version
        )
        self.async_write_ha_state()

    async def _async_install_in_phases(self, backup: bool) -> None:
        """Fake an install that goes through the phases of a real one."""
        self._attr_in_progress = True
        for phase in self._install_phases:
            if phase is UpdateInstallPhase.BACKING_UP and not backup:
                continue
            if phase is UpdateInstallPhase.DOWNLOADING:
                for step in range(self._update_steps):
                    self._attr_update_percentage = step * 100 / self._update_steps
                    await self._async_fake_phase(phase)
                self._attr_update_percentage = None
            elif phase is UpdateInstallPhase.WAITING_FOR_USER:
                await self._async_fake_phase(phase, FAKE_WAITING_FOR_USER_STEPS)
            else:
                await self._async_fake_phase(phase)

    async def _async_fake_phase(
        self, phase: UpdateInstallPhase, steps: int = 1
    ) -> None:
        """Report an install phase and fake its work."""
        self._attr_install_phase = phase
        self.async_write_ha_state()
        await _fake_install(steps)

    @override
    def release_notes(self) -> str | None:
        """Return the release notes."""
        return (
            "Long release notes.\n\n**With** "
            f"markdown support!\n\n***\n\n{self.release_summary}"
        )
