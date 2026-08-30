"""Support for Elgato firmware updates."""

from datetime import datetime
from typing import Any, override

from elgato import (
    ElgatoConnectionError,
    ElgatoError,
    ElgatoFirmwareError,
    FirmwareImage,
    FirmwareVersion,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import ELGATO_KEY
from .const import DOMAIN
from .coordinator import (
    ElgatoConfigEntry,
    ElgatoDataUpdateCoordinator,
    ElgatoFirmwareCoordinator,
)
from .entity import ElgatoEntity
from .helpers import elgato_device_action

PARALLEL_UPDATES = 1

# A device takes about a minute to come back after it swaps boot slots. This
# is the point at which one that never does stops being called installing.
REBOOT_TIMEOUT = 300


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Elgato firmware update based on a config entry."""
    async_add_entities([ElgatoUpdateEntity(entry.runtime_data, hass.data[ELGATO_KEY])])


class ElgatoUpdateEntity(ElgatoEntity, UpdateEntity):
    """Representation of the firmware on an Elgato Light.

    Elgato bumps the build number on every release but not always the version
    in front of it, so two builds of 1.0.4 are a thing. Both numbers go into
    the version string, which is what puts them in order.
    """

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _installing_build: int | None = None
    _installing_timeout: CALLBACK_TYPE | None = None
    _attr_entity_category = EntityCategory.CONFIG
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        coordinator: ElgatoDataUpdateCoordinator,
        firmware: ElgatoFirmwareCoordinator,
    ) -> None:
        """Initiate the Elgato firmware update."""
        super().__init__(coordinator)

        self.firmware = firmware
        self._attr_unique_id = coordinator.data.info.serial_number

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the firmware coordinator as well as the device one."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.firmware.async_add_listener(self._handle_coordinator_update)
        )
        # Otherwise the reboot timer outlives the entity it belongs to.
        self.async_on_remove(self._installing_finished)

    @property
    @override
    def available(self) -> bool:
        """Return if both the device and Elgato could be reached."""
        return super().available and self.firmware.last_update_success

    @override
    async def async_update(self) -> None:
        """Update the entity.

        Asking for an update check has to reach the catalog; the device
        coordinator alone knows nothing about what Elgato ships.
        """
        await super().async_update()
        await self.firmware.async_request_refresh()

    @property
    @override
    def installed_version(self) -> str:
        """Return the firmware currently on the device."""
        info = self.coordinator.data.info
        return f"{info.firmware_version}.{info.firmware_build_number}"

    @property
    @override
    def in_progress(self) -> bool:
        """Return if an install is still going on."""
        return self._installing_build is not None

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the firmware Elgato currently ships for this device.

        The catalog covers every model, so a board Elgato ships nothing for
        simply has no entry and this entity has nothing to compare against.
        """
        if (latest := self._latest) is None:
            return None
        return f"{latest.version}.{latest.build_number}"

    @property
    def _latest(self) -> FirmwareVersion | None:
        """Return the entry in the catalog for the board of this device."""
        if not (catalog := self.firmware.data):
            return None
        return catalog.get(self.coordinator.data.info.hardware_board_type)

    @elgato_device_action
    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the firmware Elgato ships for this device.

        A device answers that it accepted the reboot and then takes about a
        minute to come back. This entity keeps saying it is installing until
        the device reports the build it was given, so the old version does
        not sit there looking finished while the light is still dark.
        """
        # Before the download, not after: fetching the image is part of the
        # install, and until this says so a second call walks straight past
        # the guard that is meant to stop it.
        self._installing_build = -1
        self._attr_update_percentage = None
        self.async_write_ha_state()

        try:
            image = await self._download()
            await self.coordinator.client.update_firmware(
                image, on_progress=self._handle_progress
            )
        except ElgatoFirmwareError as err:
            # A device turns firmware away for reasons someone can act on:
            # too little battery left, an image for another model. Say which.
            self._installing_finished()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_install_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except Exception:
            self._installing_finished()
            raise
        finally:
            self.async_write_ha_state()

        self._installing_build = image.build_number
        # A device that never comes back on the new firmware would otherwise
        # leave this saying it is installing for good.
        self._installing_timeout = async_call_later(
            self.hass, REBOOT_TIMEOUT, self._installing_timed_out
        )

    async def _download(self) -> FirmwareImage:
        """Fetch the firmware image from Elgato.

        This is the half of the install that happens off the local network,
        so it reports on the coordinator that covers it and says Elgato in
        the message. Letting the handler around async_install see these would
        mark the device coordinator failed and blame the light, over a
        problem that is entirely at Elgato's end.
        """
        try:
            board_type = self.coordinator.data.info.hardware_board_type
            return await self.firmware.catalog.download(board_type)
        except ElgatoConnectionError as err:
            self.firmware.async_set_update_error(err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_communication_error",
            ) from err
        except ElgatoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_unknown_error",
            ) from err

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Notice the device coming back on its new firmware."""
        if (
            self._installing_build is not None
            and self.coordinator.last_update_success
            and self.coordinator.data.info.firmware_build_number
            >= self._installing_build
        ):
            self._installing_finished()

        super()._handle_coordinator_update()

    @callback
    def _installing_finished(self) -> None:
        """Stop reporting an install, however it ended."""
        self._installing_build = None
        self._attr_update_percentage = None
        if self._installing_timeout is not None:
            self._installing_timeout()
            self._installing_timeout = None

    @callback
    def _installing_timed_out(self, _now: datetime) -> None:
        """Give up on a device that never came back.

        This entity changed its own mind, so it publishes that itself rather
        than waiting for a coordinator update to come along and do it.
        """
        self._installing_timeout = None
        self._installing_finished()
        self.async_write_ha_state()

    @callback
    def _handle_progress(self, sent: int, total: int) -> None:
        """Report how much of the firmware the device has taken."""
        self._attr_update_percentage = round(sent / total * 100)
        self.async_write_ha_state()
