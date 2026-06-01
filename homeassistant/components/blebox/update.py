"""BleBox update entities implementation."""

from datetime import timedelta
from typing import Any, Final

from blebox_uniapi.error import ConnectionError as BleBoxConnectionError, Error
import blebox_uniapi.update

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import BleBoxConfigEntry
from .coordinator import BleBoxCoordinator
from .entity import BleBoxEntity

PARALLEL_UPDATES = 0
SCAN_INTERVAL = timedelta(hours=1)


_POLL_INTERVAL_SECONDS: Final = 10
_MAX_POLL_ATTEMPTS: Final = 30


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BleBoxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a BleBox update entry."""
    coordinator = config_entry.runtime_data
    entities = [
        BleBoxUpdateEntity(coordinator, feature)
        for feature in coordinator.box.features.get("updates", [])
    ]
    async_add_entities(entities, update_before_add=True)


class BleBoxUpdateEntity(BleBoxEntity[blebox_uniapi.update.Update], UpdateEntity):
    """Representation of BleBox updates."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    @property
    def should_poll(self) -> bool:
        """Return True because firmware versions cannot be fetched via coordinator."""
        return True

    def __init__(
        self, coordinator: BleBoxCoordinator, feature: blebox_uniapi.update.Update
    ) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator, feature)
        self._in_progress_old_version: str | None = None
        self._poll_cancel: CALLBACK_TYPE | None = None
        self._poll_attempts: int = 0

    @property
    def in_progress(self) -> bool:
        """Return True while the device hasn't yet rebooted to the new firmware."""
        return (
            self._in_progress_old_version is not None
            and self._in_progress_old_version == self._feature.installed_version
        )

    def _sync_sw_version(self) -> None:
        """Sync installed firmware version to the device registry."""
        if self.device_entry:
            dr.async_get(self.hass).async_update_device(
                self.device_entry.id,
                sw_version=self._feature.installed_version,
            )

    async def async_update(self) -> None:
        """Update state and refresh sw_version in device registry."""
        try:
            await self._feature.async_update()
        except Error as ex:
            raise HomeAssistantError(ex) from ex
        self._sync_sw_version()

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self._feature.installed_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self._feature.latest_version

    def _cancel_poll(self) -> None:
        if self._poll_cancel is not None:
            self._poll_cancel()
            self._poll_cancel = None

    def _reset_progress(self) -> None:
        self._in_progress_old_version = None
        self._poll_attempts = 0
        self.async_write_ha_state()

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._cancel_poll()
        self._in_progress_old_version = self._feature.installed_version
        self._poll_attempts = 0
        self.async_write_ha_state()
        try:
            await self._feature.async_install()
        except Error as ex:
            self._reset_progress()
            raise HomeAssistantError(ex) from ex
        self._poll_cancel = async_call_later(
            self.hass, _POLL_INTERVAL_SECONDS, self._poll_until_updated
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending poll timer when the entity is removed."""
        self._cancel_poll()

    async def _poll_until_updated(self, _now: Any) -> None:
        """Poll device until the installed version changes after OTA reboot."""
        self._poll_cancel = None
        self._poll_attempts += 1
        try:
            await self._feature.async_update()
        except BleBoxConnectionError:
            pass
        except Error:
            self._reset_progress()
            return
        else:
            self._sync_sw_version()
        if self.in_progress and self._poll_attempts < _MAX_POLL_ATTEMPTS:
            self._poll_cancel = async_call_later(
                self.hass, _POLL_INTERVAL_SECONDS, self._poll_until_updated
            )
        else:
            self._reset_progress()
