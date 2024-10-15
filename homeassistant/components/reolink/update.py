"""Update entities for Reolink devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from reolink_aio.exceptions import ReolinkError
from reolink_aio.software_version import NewSoftwareVersion

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData

POLL_AFTER_INSTALL = 120


@dataclass(frozen=True, kw_only=True)
class ReolinkUpdateEntityDescription(
    UpdateEntityDescription,
    ReolinkChannelEntityDescription,
):
    """A class that describes update entities."""


@dataclass(frozen=True, kw_only=True)
class ReolinkHostUpdateEntityDescription(
    UpdateEntityDescription,
    ReolinkHostEntityDescription,
):
    """A class that describes host update entities."""


UPDATE_ENTITIES = (
    ReolinkUpdateEntityDescription(
        key="firmware",
        supported=lambda api, ch: api.supported(ch, "firmware"),
        device_class=UpdateDeviceClass.FIRMWARE,
    ),
)

HOST_UPDATE_ENTITIES = (
    ReolinkHostUpdateEntityDescription(
        key="firmware",
        supported=lambda api: api.supported(None, "firmware"),
        device_class=UpdateDeviceClass.FIRMWARE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ReolinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up update entities for Reolink component."""
    reolink_data: ReolinkData = config_entry.runtime_data

    entities: list[ReolinkUpdateEntity | ReolinkHostUpdateEntity] = [
        ReolinkUpdateEntity(reolink_data, channel, entity_description)
        for entity_description in UPDATE_ENTITIES
        for channel in reolink_data.host.api.channels
        if entity_description.supported(reolink_data.host.api, channel)
    ]
    entities.extend(
        ReolinkHostUpdateEntity(reolink_data, entity_description)
        for entity_description in HOST_UPDATE_ENTITIES
        if entity_description.supported(reolink_data.host.api)
    )
    async_add_entities(entities)


class ReolinkUpdateEntity(
    ReolinkChannelCoordinatorEntity,
    UpdateEntity,
):
    """Base update entity class for Reolink IP cameras."""

    entity_description: ReolinkUpdateEntityDescription
    _attr_release_url = "https://reolink.com/download-center/"

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkUpdateEntityDescription,
    ) -> None:
        """Initialize Reolink update entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, channel, reolink_data.firmware_coordinator)
        self._cancel_update: CALLBACK_TYPE | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._host.api.camera_sw_version(self._channel)

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_firmware = self._host.api.firmware_update_available(self._channel)
        if not new_firmware:
            return self.installed_version

        if isinstance(new_firmware, str):
            return new_firmware

        return new_firmware.version_string

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        supported_features = UpdateEntityFeature.INSTALL
        new_firmware = self._host.api.firmware_update_available(self._channel)
        if isinstance(new_firmware, NewSoftwareVersion):
            supported_features |= UpdateEntityFeature.RELEASE_NOTES
        return supported_features

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        new_firmware = self._host.api.firmware_update_available(self._channel)
        assert isinstance(new_firmware, NewSoftwareVersion)

        return (
            "If the install button fails, download this"
            f" [firmware zip file]({new_firmware.download_url})."
            " Then, follow the installation guide (PDF in the zip file).\n\n"
            f"## Release notes\n\n{new_firmware.release_notes}"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        try:
            await self._host.api.update_firmware(self._channel)
        except ReolinkError as err:
            raise HomeAssistantError(
                f"Error trying to update Reolink firmware: {err}"
            ) from err
        finally:
            self.async_write_ha_state()
            self._cancel_update = async_call_later(
                self.hass, POLL_AFTER_INSTALL, self._async_update_future
            )

    async def _async_update_future(self, now: datetime | None = None) -> None:
        """Request update."""
        await self.async_update()

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        self._host.firmware_ch_list.append(self._channel)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        await super().async_will_remove_from_hass()
        if self._channel in self._host.firmware_ch_list:
            self._host.firmware_ch_list.remove(self._channel)
        if self._cancel_update is not None:
            self._cancel_update()


class ReolinkHostUpdateEntity(
    ReolinkHostCoordinatorEntity,
    UpdateEntity,
):
    """Update entity class for Reolink Host."""

    entity_description: ReolinkHostUpdateEntityDescription
    _attr_release_url = "https://reolink.com/download-center/"

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostUpdateEntityDescription,
    ) -> None:
        """Initialize Reolink update entity."""
        self.entity_description = entity_description
        super().__init__(reolink_data, reolink_data.firmware_coordinator)
        self._cancel_update: CALLBACK_TYPE | None = None

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        return self._host.api.sw_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        new_firmware = self._host.api.firmware_update_available()
        if not new_firmware:
            return self.installed_version

        if isinstance(new_firmware, str):
            return new_firmware

        return new_firmware.version_string

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        supported_features = UpdateEntityFeature.INSTALL
        new_firmware = self._host.api.firmware_update_available()
        if isinstance(new_firmware, NewSoftwareVersion):
            supported_features |= UpdateEntityFeature.RELEASE_NOTES
        return supported_features

    async def async_release_notes(self) -> str | None:
        """Return the release notes."""
        new_firmware = self._host.api.firmware_update_available()
        assert isinstance(new_firmware, NewSoftwareVersion)

        return (
            "If the install button fails, download this"
            f" [firmware zip file]({new_firmware.download_url})."
            " Then, follow the installation guide (PDF in the zip file).\n\n"
            f"## Release notes\n\n{new_firmware.release_notes}"
        )

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        try:
            await self._host.api.update_firmware()
        except ReolinkError as err:
            raise HomeAssistantError(
                f"Error trying to update Reolink firmware: {err}"
            ) from err
        finally:
            self.async_write_ha_state()
            self._cancel_update = async_call_later(
                self.hass, POLL_AFTER_INSTALL, self._async_update_future
            )

    async def _async_update_future(self, now: datetime | None = None) -> None:
        """Request update."""
        await self.async_update()

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        self._host.firmware_ch_list.append(None)

    async def async_will_remove_from_hass(self) -> None:
        """Entity removed."""
        await super().async_will_remove_from_hass()
        if None in self._host.firmware_ch_list:
            self._host.firmware_ch_list.remove(None)
        if self._cancel_update is not None:
            self._cancel_update()
