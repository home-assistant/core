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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create update entities."""

    coordinator = entry.runtime_data.firmware_coordinator
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
    def installed_version(self) -> str | None:
        """Return the current firmware version."""
        return self.coordinator.device.firmware[
            self.entity_description.component
        ].current_version

    @property
    def latest_version(self) -> str:
        """Return the latest firmware version."""
        return self.coordinator.device.firmware[
            self.entity_description.component
        ].latest_version

    @property
    def release_url(self) -> str | None:
        """Return the release notes URL."""
        return "https://support-iot.lamarzocco.com/firmware-updates/"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        self.async_write_ha_state()
        try:
            success = await self.coordinator.device.update_firmware(
                self.entity_description.component
            )
        except RequestNotSuccessful as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            ) from exc
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "key": self.entity_description.key,
                },
            )
        self._attr_in_progress = False
        await self.coordinator.async_request_refresh()
