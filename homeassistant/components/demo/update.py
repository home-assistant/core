"""Demo platform that offers fake update entities."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN

FAKE_INSTALL_SLEEP_TIME = 0.5


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
            ),
        ]
    )


async def _fake_install() -> None:
    """Fake install an update."""
    await asyncio.sleep(FAKE_INSTALL_SLEEP_TIME)


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
    ) -> None:
        """Initialize the Demo select entity."""
        self._attr_installed_version = installed_version
        self._attr_device_class = device_class
        self._attr_latest_version = latest_version
        self._attr_release_summary = release_summary
        self._attr_release_url = release_url
        self._attr_title = title
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
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

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if self.supported_features & UpdateEntityFeature.PROGRESS:
            for progress in range(0, 100, 10):
                self._attr_in_progress = progress
                self.async_write_ha_state()
                await _fake_install()

        self._attr_in_progress = False
        self._attr_installed_version = (
            version if version is not None else self.latest_version
        )
        self.async_write_ha_state()

    def release_notes(self) -> str | None:
        """Return the release notes."""
        return (
            "Long release notes.\n\n**With** "
            f"markdown support!\n\n***\n\n{self.release_summary}"
        )
