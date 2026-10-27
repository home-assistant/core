"""Support for Rituals Perfume Genie firmware updates."""

from datetime import datetime, timedelta
from typing import Any, override

from ritualsgenie import RitualsGenieError, RitualsGenieFirmware

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import RitualsConfigEntry
from .entity import DiffuserEntity, async_add_diffusers

PARALLEL_UPDATES = 1

# Rituals doesn't report progress; the new firmware only shows up once the
# diffuser runs it. One that never does stops being called installing here.
INSTALL_TIMEOUT = timedelta(minutes=30)

ENTITY_DESCRIPTION = UpdateEntityDescription(
    key="firmware",
    device_class=UpdateDeviceClass.FIRMWARE,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser firmware updates."""
    hubs = config_entry.runtime_data.hubs

    @callback
    def add_diffusers(hublots: list[str]) -> None:
        async_add_entities(
            RitualsUpdateEntity(hubs, hublot, ENTITY_DESCRIPTION) for hublot in hublots
        )

    async_add_diffusers(config_entry, add_diffusers)


def _version(firmware: RitualsGenieFirmware, current: bool) -> str | None:
    """Return a firmware version, with its ID when Rituals numbers both.

    Two builds can carry the same version. Only with the ID in there they
    tell apart, otherwise an update between them would look like none.
    """
    version = firmware.current if current else firmware.newest
    if version is None:
        return None

    if firmware.current_id is None or firmware.newest_id is None:
        return str(version)

    firmware_id = firmware.current_id if current else firmware.newest_id
    return f"{version} ({firmware_id})"


class RitualsUpdateEntity(DiffuserEntity, UpdateEntity):
    """Representation of the firmware of a diffuser."""

    # Progress without a percentage: Rituals only tells when it is done.
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    _installing: bool = False
    _installing_timeout: CALLBACK_TYPE | None = None

    @override
    async def async_added_to_hass(self) -> None:
        """Stop the install timer together with the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self._installing_finished)

    @property
    def _firmware(self) -> RitualsGenieFirmware | None:
        """Return the firmware details of the diffuser."""
        return self.hub.firmware

    @property
    @override
    def installed_version(self) -> str | None:
        """Return the firmware the diffuser runs."""
        if (firmware := self._firmware) is None:
            return None

        return _version(firmware, current=True)

    @property
    @override
    def latest_version(self) -> str | None:
        """Return the newest firmware Rituals has for the diffuser."""
        if (firmware := self._firmware) is None:
            return None

        return _version(firmware, current=False)

    @property
    @override
    def in_progress(self) -> bool:
        """Return if an install is still going on."""
        return self._installing

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return if the newest firmware is newer than the installed one.

        Rituals numbers its firmware as well, which is more reliable than
        comparing version strings like "5.4-rc4".
        """
        if (firmware := self._firmware) and (
            available := firmware.update_available
        ) is not None:
            return available

        return super().version_is_newer(latest_version, installed_version)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Have Rituals install its newest firmware on the diffuser."""
        try:
            await self.coordinator.client.update_firmware(self.hub.hash)
        except RitualsGenieError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="firmware_update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        self._installing = True
        self._installing_timeout = async_call_later(
            self.hass, INSTALL_TIMEOUT, self._installing_timed_out
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Notice the diffuser running its new firmware."""
        if self.available:
            self._sync_device_firmware()

            # Done once the diffuser runs the newest firmware. Unknown
            # versions don't count as done: they might be on their way.
            if (
                self._installing
                and self.installed_version is not None
                and self.latest_version is not None
                and not self.has_update
            ):
                self._installing_finished()

        super()._handle_coordinator_update()

    @callback
    def _sync_device_firmware(self) -> None:
        """Tell the device registry what the diffuser runs now.

        The device info is only read when the entity is added, so without
        this the device page keeps the firmware it had at setup.
        """
        if (firmware := self._firmware) is None or firmware.current is None:
            return

        # Without the ID, the same as the device info has it.
        version = str(firmware.current)
        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier(
            (DOMAIN, self.hublot), self.coordinator.config_entry.entry_id
        )
        if device is not None and device.sw_version != version:
            registry.async_update_device(device.id, sw_version=version)

    @callback
    def _installing_finished(self) -> None:
        """Stop reporting an install, however it ended."""
        self._installing = False
        if self._installing_timeout is not None:
            self._installing_timeout()
            self._installing_timeout = None

    @callback
    def _installing_timed_out(self, _now: datetime) -> None:
        """Give up on a diffuser that never reported its new firmware."""
        self._installing_timeout = None
        self._installing_finished()
        self.async_write_ha_state()
