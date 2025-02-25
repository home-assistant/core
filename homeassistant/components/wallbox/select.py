"""Home Assistant component for accessing the Wallbox Portal API. The switch component creates a switch entity."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CHARGER_DATA_KEY,
    CHARGER_ECO_SMART_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_SOLAR_CHARGING_MODE,
    DOMAIN,
    EcoSmartMode,
)
from .coordinator import WallboxCoordinator
from .entity import WallboxEntity

SELECT_TYPES: dict[str, SelectEntityDescription] = {
    CHARGER_ECO_SMART_KEY: SelectEntityDescription(
        key=CHARGER_ECO_SMART_KEY,
        translation_key="eco_smart",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create wallbox select entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [WallboxSelect(coordinator, SELECT_TYPES[CHARGER_ECO_SMART_KEY])]
    )


class WallboxSelect(WallboxEntity, SelectEntity):
    """Representation of the Wallbox portal."""

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize a Wallbox select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"
        self._attr_icon = "mdi:solar-power"
        self._attr_options = [
            EcoSmartMode.OFF,
            EcoSmartMode.ECO_MODE,
            EcoSmartMode.FULL_SOLAR,
        ]

    @property
    def available(self) -> bool:
        """Return the availability of the select entity."""
        return (
            super().available
            and CHARGER_POWER_BOOST_KEY
            in self.coordinator.data[CHARGER_DATA_KEY][CHARGER_PLAN_KEY][
                CHARGER_FEATURES_KEY
            ]
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return str(self.coordinator.data[CHARGER_SOLAR_CHARGING_MODE])

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option == EcoSmartMode.ECO_MODE:
            await self.coordinator.async_set_eco_smart(True, 0)
        elif option == EcoSmartMode.FULL_SOLAR:
            await self.coordinator.async_set_eco_smart(True, 1)
        else:
            await self.coordinator.async_set_eco_smart(False)
