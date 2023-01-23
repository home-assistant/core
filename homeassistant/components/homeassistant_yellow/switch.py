"""Support for Home Assistant Yellow LED control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.hassio import async_set_yellow_settings
from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .models import YellowData

SWITCHES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="disk_led",
        device_class=SwitchDeviceClass.SWITCH,
        name="Disk LED",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="heartbeat_led",
        device_class=SwitchDeviceClass.SWITCH,
        name="Heartbeat LED",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="power_led",
        device_class=SwitchDeviceClass.SWITCH,
        name="Power LED",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Home Assistant Yellow switch platform."""
    yellow_data: YellowData = hass.data[DOMAIN]
    entities: list[YellowEnableSwitchEntity] = []
    for switch in SWITCHES:
        entities.append(
            YellowEnableSwitchEntity(
                coordinator=yellow_data.coordinator,
                description=switch,
            )
        )
    async_add_entities(entities)


class YellowEnableSwitchEntity(
    SwitchEntity, CoordinatorEntity[DataUpdateCoordinator[dict[str, bool]]]
):
    """A representation of an Yellow LED enable/disable switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, bool]],
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_name = description.name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, DOMAIN)},
            "manufacturer": "Nabu Casa",
            "model": "Home Assistant Yellow",
            "name": "Yellow",
        }
        self._attr_unique_id = description.key
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Get whether the LED is enabled."""
        return self.coordinator.data[self.entity_description.key]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the LED."""
        settings = self.coordinator.data
        settings[self.entity_description.key] = False
        await async_set_yellow_settings(self.hass, settings)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the LED."""
        settings = self.coordinator.data
        settings[self.entity_description.key] = True
        await async_set_yellow_settings(self.hass, settings)
