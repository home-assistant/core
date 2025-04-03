"""Support for La Marzocco update entities."""

from dataclasses import dataclass
from typing import Any

from pylamarzocco.const import FirmwareType
from pylamarzocco.exceptions import RequestNotSuccessful

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoUpdateEntityDescription(
    LaMarzoccoEntityDescription,
    UpdateEntityDescription,
):
    """Description of a La Marzocco update entities."""

    component: FirmwareType


ENTITIES: tuple[LaMarzoccoUpdateEntityDescription, ...] = (
    LaMarzoccoUpdateEntityDescription(
        key="machine_firmware",
        translation_key="machine_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        component=FirmwareType.MACHINE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoUpdateEntityDescription(
        key="gateway_firmware",
        translation_key="gateway_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        component=FirmwareType.GATEWAY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create update entities."""

    coordinator = entry.runtime_data.settings_coordinator
    async_add_entities(
        LaMarzoccoUpdateEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoUpdateEntity(LaMarzoccoEntity, UpdateEntity):
    """Entity representing the update state."""

    entity_description: LaMarzoccoUpdateEntityDescription
    _attr_supported_features = UpdateEntityFeature.INSTALL

    @property
    def installed_version(self) -> str:
        """Return the current firmware version."""
        return self.coordinator.device.settings.firmwares[
            self.entity_description.component
        ].build_version

    @property
    def latest_version(self) -> str:
        """Return the latest firmware version."""
        if available_update := self.coordinator.device.settings.firmwares[
            self.entity_description.component
        ].available_update:
            return available_update.build_version
        return self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            await self.coordinator.device.update_firmware()
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc
        self._attr_in_progress = False
        await self.coordinator.async_request_refresh()
