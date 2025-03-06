"""Home Assistant component for accessing the Wallbox Portal API. The switch component creates a switch entity."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CHARGER_DATA_KEY,
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


@dataclass(frozen=True)
class WallboxSelectEntityDescription(SelectEntityDescription):
    """Describes Wallbox select entity."""

    current_option_fn: Callable[[WallboxCoordinator], str | None]
    select_option_fn: Callable[[WallboxCoordinator, str], Awaitable[None]]


SELECT_TYPES: dict[str, WallboxSelectEntityDescription] = {
    CHARGER_SOLAR_CHARGING_MODE: WallboxSelectEntityDescription(
        key=CHARGER_SOLAR_CHARGING_MODE,
        translation_key="eco_smart",
        select_option_fn=lambda coordinator, mode: coordinator.async_set_eco_smart(
            mode
        ),
        options=[
            EcoSmartMode.OFF,
            EcoSmartMode.ECO_MODE,
            EcoSmartMode.FULL_SOLAR,
        ],
        current_option_fn=lambda coordinator: coordinator.data[
            CHARGER_SOLAR_CHARGING_MODE
        ],
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create wallbox select entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        WallboxSelect(coordinator, entry, description)
        for ent in coordinator.data
        if (description := SELECT_TYPES.get(ent))
    )


class WallboxSelect(WallboxEntity, SelectEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSelectEntityDescription

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: WallboxSelectEntityDescription,
    ) -> None:
        """Initialize a Wallbox select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

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
        """Return an option."""
        return self.entity_description.current_option_fn(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        """Handle the selection of an option."""
        try:
            await self.entity_description.select_option_fn(self.coordinator, option)
        except Exception as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
