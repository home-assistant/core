"""Support for Daikin firmware update entities."""

import logging
from typing import TYPE_CHECKING, Any, override

from daikin_onecta.models import ManagementPoint

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity_descriptions import UPDATE_DESCRIPTIONS

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo


_LOGGER = logging.getLogger(__name__)

# The Daikin Onecta cloud API exposes firmware updates


def migrate_legacy_update_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Remove the redundant update suffix from existing firmware update IDs."""
    entity_registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):
        if entry.domain != "update" or entry.platform != DOMAIN:
            continue
        if not entry.unique_id.endswith("_firmware_update"):
            continue
        new_unique_id = entry.unique_id.removesuffix("_update")
        if entity_registry.async_get_entity_id("update", DOMAIN, new_unique_id):
            continue
        entity_registry.async_update_entity(
            entry.entity_id, new_unique_id=new_unique_id
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin update entities from a config entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data

    entities = [
        DaikinFirmwareUpdateEntity(
            coordinator,
            device,
            management_point,
            management_point.management_point_type,
        )
        for device in (coordinator.data or {}).values()
        for management_point in device.device.management_points
        if management_point.firmware_version is not None
        or management_point.software_version is not None
    ]

    async_add_entities(entities)


class DaikinFirmwareUpdateEntity(CoordinatorEntity, UpdateEntity):
    """Represents the gateway firmware for a single Daikin device."""

    def __init__(
        self,
        coordinator: OnectaDataUpdateCoordinator,
        device: DaikinOnectaDevice,
        gateway_mp: ManagementPoint,
        management_point_type: str,
    ) -> None:
        """Initialise the update entity."""
        super().__init__(coordinator)
        self._device = device
        self._coordinator = coordinator
        self._management_point_type = management_point_type
        self._embedded_id = gateway_mp.embedded_id
        mpt = management_point_type[0].upper() + management_point_type[1:]
        assert self._device.ha_device_id is not None
        self._attr_device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, self._device.id + self._embedded_id)},
            "name": self._device.name + " " + mpt,
            "via_device_id": self._device.ha_device_id,
        }
        self._device.fill_device_info(self._attr_device_info, self._embedded_id)
        self._attr_has_entity_name = True
        self.entity_description = UPDATE_DESCRIPTIONS["FirmwareUpdate"]

        self._attr_unique_id = f"{device.id}_{self._embedded_id}_firmware"

        # Populate initial state
        self._update_from_management_point(gateway_mp)

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Trigger a firmware update via the Daikin Onecta cloud API."""
        if not self._is_update_supported or self._firmware_id is None:
            _LOGGER.error(
                "Cannot install firmware for %s: update is not supported or no firmware ID is available",
                self._device.name,
            )
            return

        _LOGGER.debug(
            "Requesting firmware update for %s, firmware id %s",
            self._device.name,
            self._firmware_id,
        )

        self._attr_in_progress = await self._device.put(
            self._device.id,
            self._embedded_id,
            f"firmware/{self._firmware_id}",
        )

        if not self._attr_in_progress:
            _LOGGER.error("Failed to trigger firmware update for %s", self._device.name)

        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_from_management_point(self, management_point: ManagementPoint) -> None:
        """Pull the latest values out of a typed management point."""
        installed = (
            management_point.firmware_version or management_point.software_version
        )
        self._attr_installed_version = (
            installed.value if installed is not None else None
        )
        supported = management_point.is_firmware_update_supported
        self._is_update_supported = (
            bool(supported.value) if supported is not None else False
        )
        self._attr_latest_version = self._attr_installed_version
        self._attr_release_url = None
        self._attr_release_summary = None
        self._firmware_id = None
        self._attr_in_progress = False
        self._attr_supported_features = (
            UpdateEntityFeature.INSTALL
            if self._is_update_supported
            else UpdateEntityFeature(0)
        )
        self._attr_extra_state_attributes = {}

        if management_point.firmware_update is not None:
            firmware_update = management_point.firmware_update.value
            self._attr_latest_version = firmware_update.get(
                "version", self._attr_latest_version
            )
            self._attr_release_summary = firmware_update.get("description")
            self._firmware_id = firmware_update.get("id")
            if firmware_update_type := firmware_update.get("type"):
                self._attr_extra_state_attributes["firmware_update_type"] = (
                    firmware_update_type
                )

        if management_point.firmware_update_status is not None:
            self._attr_in_progress = (
                management_point.firmware_update_status.value == "in-progress"
            )
            self._attr_supported_features |= UpdateEntityFeature.PROGRESS

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        mp = self._device.management_point(self._embedded_id)
        if mp is not None:
            self._update_from_management_point(mp)
        self.async_write_ha_state()

    @property
    @override
    def available(self) -> bool:
        """Return whether the source device is available."""
        return super().available and self._device.available
