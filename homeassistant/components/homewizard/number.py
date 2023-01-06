"""Creates HomeWizard Number entities."""
from __future__ import annotations

from typing import Optional, cast

from homewizard_energy.errors import DisabledError, RequestError

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HWEnergyDeviceUpdateCoordinator
from .entity import HomeWizardEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers for device."""
    coordinator: HWEnergyDeviceUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    if coordinator.data["state"]:
        async_add_entities(
            [
                HWEnergyNumberEntity(coordinator, entry),
            ]
        )


class HWEnergyNumberEntity(HomeWizardEntity, NumberEntity):
    """Representation of status light number."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HWEnergyDeviceUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the control number."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.unique_id}_status_light_brightness"
        self._attr_name = "Status light brightness"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:lightbulb-on"

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        try:
            await self.coordinator.api.state_set(brightness=value * (255 / 100))
        except RequestError as ex:
            raise HomeAssistantError from ex
        except DisabledError as ex:
            await self.hass.config_entries.async_reload(self.coordinator.entry_id)
            raise HomeAssistantError from ex

        await self.coordinator.async_refresh()

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        brightness = cast(Optional[float], self.coordinator.data["state"].brightness)
        if brightness is None:
            return None
        return round(brightness * (100 / 255))
