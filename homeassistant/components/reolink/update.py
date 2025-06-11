"""Update entities for Reolink devices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reolink_aio.exceptions import ReolinkError
from reolink_aio.software_version import NewSoftwareVersion, SoftwareVersion

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DEVICE_UPDATE_INTERVAL
from .const import DOMAIN
from .entity import (
    ReolinkChannelCoordinatorEntity,
    ReolinkChannelEntityDescription,
    ReolinkHostCoordinatorEntity,
    ReolinkHostEntityDescription,
)
from .util import ReolinkConfigEntry, ReolinkData, raise_translated_error

PARALLEL_UPDATES = 0
RESUME_AFTER_INSTALL = 15
POLL_AFTER_INSTALL = 120
POLL_PROGRESS = 2


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
    async_add_entities: AddConfigEntryEntitiesCallback,
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


class ReolinkUpdateBaseEntity(
    CoordinatorEntity[DataUpdateCoordinator[None]], UpdateEntity
):
    """Base update entity class for Reolink."""

    _attr_release_url = "https://reolink.com/download-center/"

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int | None,
        coordinator: DataUpdateCoordinator[None],
    ) -> None:
        """Initialize Reolink update entity."""
        CoordinatorEntity.__init__(self, coordinator)
        self._channel = channel
        self._host = reolink_data.host
        self._cancel_update: CALLBACK_TYPE | None = None
        self._cancel_resume: CALLBACK_TYPE | None = None
        self._cancel_progress: CALLBACK_TYPE | None = None
        self._installing: bool = False
        self._reolink_data = reolink_data

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
    def in_progress(self) -> bool:
        """Update installation progress."""
        return self._host.api.sw_upload_progress(self._channel) < 100

    @property
    def update_percentage(self) -> int:
        """Update installation progress."""
        return self._host.api.sw_upload_progress(self._channel)

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Flag supported features."""
        supported_features = UpdateEntityFeature.INSTALL
        new_firmware = self._host.api.firmware_update_available(self._channel)
        if isinstance(new_firmware, NewSoftwareVersion):
            supported_features |= UpdateEntityFeature.RELEASE_NOTES
            supported_features |= UpdateEntityFeature.PROGRESS
        return supported_features

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self._installing or self._cancel_update is not None:
            return True
        return super().available

    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        try:
            installed = SoftwareVersion(installed_version)
            latest = SoftwareVersion(latest_version)
        except ReolinkError:
            # when the online update API returns a unexpected string
            return True

        return latest > installed

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

    @raise_translated_error
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        self._installing = True
        await self._pause_update_coordinator()
        self._cancel_progress = async_call_later(
            self.hass, POLL_PROGRESS, self._async_update_progress
        )
        try:
            await self._host.api.update_firmware(self._channel)
        except ReolinkError as err:
            if err.translation_key:
                raise
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_install_error",
                translation_placeholders={"err": str(err)},
            ) from err
        finally:
            self.async_write_ha_state()
            self._cancel_update = async_call_later(
                self.hass, POLL_AFTER_INSTALL, self._async_update_future
            )
            self._cancel_resume = async_call_later(
                self.hass, RESUME_AFTER_INSTALL, self._resume_update_coordinator
            )
            self._installing = False

    async def _pause_update_coordinator(self) -> None:
        """Pause updating the states using the data update coordinator (during reboots)."""
        self._reolink_data.device_coordinator.update_interval = None
        self._reolink_data.device_coordinator.async_set_updated_data(None)

    async def _resume_update_coordinator(self, *args: Any) -> None:
        """Resume updating the states using the data update coordinator (after reboots)."""
        self._reolink_data.device_coordinator.update_interval = DEVICE_UPDATE_INTERVAL
        try:
            await self._reolink_data.device_coordinator.async_refresh()
        finally:
            self._cancel_resume = None

    async def _async_update_progress(self, *args: Any) -> None:
        """Request update."""
        self.async_write_ha_state()
        if self._installing:
            self._cancel_progress = async_call_later(
                self.hass, POLL_PROGRESS, self._async_update_progress
            )

    async def _async_update_future(self, *args: Any) -> None:
        """Request update."""
        try:
            await self.async_update()
        finally:
            self._cancel_update = None

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
        if self._cancel_progress is not None:
            self._cancel_progress()
        if self._cancel_resume is not None:
            self._cancel_resume()


class ReolinkUpdateEntity(
    ReolinkUpdateBaseEntity,
    ReolinkChannelCoordinatorEntity,
):
    """Base update entity class for Reolink IP cameras."""

    entity_description: ReolinkUpdateEntityDescription
    _channel: int

    def __init__(
        self,
        reolink_data: ReolinkData,
        channel: int,
        entity_description: ReolinkUpdateEntityDescription,
    ) -> None:
        """Initialize Reolink update entity."""
        self.entity_description = entity_description
        ReolinkUpdateBaseEntity.__init__(
            self, reolink_data, channel, reolink_data.firmware_coordinator
        )
        ReolinkChannelCoordinatorEntity.__init__(
            self, reolink_data, channel, reolink_data.firmware_coordinator
        )


class ReolinkHostUpdateEntity(
    ReolinkUpdateBaseEntity,
    ReolinkHostCoordinatorEntity,
):
    """Update entity class for Reolink Host."""

    entity_description: ReolinkHostUpdateEntityDescription

    def __init__(
        self,
        reolink_data: ReolinkData,
        entity_description: ReolinkHostUpdateEntityDescription,
    ) -> None:
        """Initialize Reolink update entity."""
        self.entity_description = entity_description
        ReolinkUpdateBaseEntity.__init__(
            self, reolink_data, None, reolink_data.firmware_coordinator
        )
        ReolinkHostCoordinatorEntity.__init__(
            self, reolink_data, reolink_data.firmware_coordinator
        )
