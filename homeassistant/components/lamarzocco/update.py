"""Support for La Marzocco update entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lmcloud import LMCloud as LaMarzoccoClient
from lmcloud.const import LaMarzoccoUpdateableComponent

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoUpdateEntityDescription(
    LaMarzoccoEntityDescription,
    UpdateEntityDescription,
):
    """Description of a La Marzocco update entities."""

    current_fw_fn: Callable[[LaMarzoccoClient], str]
    latest_fw_fn: Callable[[LaMarzoccoClient], str]
    component: LaMarzoccoUpdateableComponent


ENTITIES: tuple[LaMarzoccoUpdateEntityDescription, ...] = (
    LaMarzoccoUpdateEntityDescription(
        key="machine_firmware",
        translation_key="machine_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        current_fw_fn=lambda lm: lm.firmware_version,
        latest_fw_fn=lambda lm: lm.latest_firmware_version,
        component=LaMarzoccoUpdateableComponent.MACHINE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoUpdateEntityDescription(
        key="gateway_firmware",
        translation_key="gateway_firmware",
        device_class=UpdateDeviceClass.FIRMWARE,
        current_fw_fn=lambda lm: lm.gateway_version,
        latest_fw_fn=lambda lm: lm.latest_gateway_version,
        component=LaMarzoccoUpdateableComponent.GATEWAY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create update entities."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
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
        return self.entity_description.current_fw_fn(self.coordinator.lm)

    @property
    def latest_version(self) -> str:
        """Return the latest firmware version."""
        return self.entity_description.latest_fw_fn(self.coordinator.lm)

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        self.async_write_ha_state()
        success = await self.coordinator.lm.update_firmware(
            self.entity_description.component
        )
        if not success:
            raise HomeAssistantError("Update failed")
        self._attr_in_progress = False
        await self.coordinator.async_request_refresh()
