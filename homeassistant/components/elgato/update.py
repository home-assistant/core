"""Support for Elgato firmware updates."""

from typing import Any, override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElgatoConfigEntry, ElgatoCoordinators
from .entity import ElgatoEntity
from .helpers import elgato_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Elgato firmware update based on a config entry."""
    async_add_entities([ElgatoUpdateEntity(entry.runtime_data)])


class ElgatoUpdateEntity(ElgatoEntity, UpdateEntity):
    """Representation of the firmware on an Elgato Light.

    Elgato bumps the build number on every release but not always the version
    in front of it, so two builds of 1.0.4 are a thing. Both numbers go into
    the version string, which is what puts them in order.
    """

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, coordinators: ElgatoCoordinators) -> None:
        """Initiate the Elgato firmware update."""
        super().__init__(coordinators.device)

        self.firmware = coordinators.firmware
        self._attr_unique_id = coordinators.device.data.info.serial_number

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the firmware coordinator as well as the device one."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.firmware.async_add_listener(self._handle_coordinator_update)
        )

    @property
    @override
    def available(self) -> bool:
        """Return if both the device and Elgato could be reached.

        This entity is the one place the two meet, so it is unavailable when
        either end is. The light itself only depends on the device, and keeps
        working when Elgato is having a day.
        """
        return (
            self.coordinator.last_update_success and self.firmware.last_update_success
        )

    @property
    @override
    def installed_version(self) -> str:
        """Return the firmware currently on the device."""
        info = self.coordinator.data.info
        return f"{info.firmware_version}.{info.firmware_build_number}"

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the firmware Elgato currently ships for this device."""
        if (latest := self.firmware.data) is None:
            return None
        return f"{latest.version}.{latest.build_number}"

    @elgato_exception_handler
    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the firmware Elgato ships for this device."""
        # Before the download, not after: fetching the image is part of the
        # install, and until this says so a second call walks straight past
        # the guard that is meant to stop it.
        self._attr_in_progress = True
        self._attr_update_percentage = None
        self.async_write_ha_state()

        try:
            image = await self.firmware.catalog.download(self.firmware.board_type)
            await self.coordinator.client.update_firmware(
                image, on_progress=self._handle_progress
            )
        finally:
            self._attr_in_progress = False
            self._attr_update_percentage = None
            self.async_write_ha_state()

    @callback
    def _handle_progress(self, sent: int, total: int) -> None:
        """Report how much of the firmware the device has taken."""
        self._attr_update_percentage = round(sent / total * 100)
        self.async_write_ha_state()
