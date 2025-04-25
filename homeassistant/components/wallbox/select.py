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
    CHARGER_ECO_SMART_KEY,
    CHARGER_FEATURES_KEY,
    CHARGER_PLAN_KEY,
    CHARGER_POWER_BOOST_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    DOMAIN,
    EcoSmartMode,
)
from .coordinator import WallboxCoordinator
from .entity import WallboxEntity


@dataclass(frozen=True, kw_only=True)
class WallboxSelectEntityDescription(SelectEntityDescription):
    """Describes Wallbox select entity."""

    current_option_fn: Callable[[WallboxCoordinator], str | None]
    select_option_fn: Callable[[WallboxCoordinator, str], Awaitable[None]]
    supported_fn: Callable[[WallboxCoordinator], bool]


SELECT_TYPES: dict[str, WallboxSelectEntityDescription] = {
    CHARGER_ECO_SMART_KEY: WallboxSelectEntityDescription(
        key=CHARGER_ECO_SMART_KEY,
        translation_key=CHARGER_ECO_SMART_KEY,
        options=[
            EcoSmartMode.OFF,
            EcoSmartMode.ECO_MODE,
            EcoSmartMode.FULL_SOLAR,
        ],
        select_option_fn=lambda coordinator, mode: coordinator.async_set_eco_smart(
            mode
        ),
        current_option_fn=lambda coordinator: coordinator.data[CHARGER_ECO_SMART_KEY],
        supported_fn=lambda coordinator: coordinator.data[CHARGER_DATA_KEY][
            CHARGER_PLAN_KEY
        ][CHARGER_FEATURES_KEY].count(CHARGER_POWER_BOOST_KEY),
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
        WallboxSelect(coordinator, description)
        for ent in coordinator.data
        if (
            (description := SELECT_TYPES.get(ent))
            and description.supported_fn(coordinator)
        )
    )


class WallboxSelect(WallboxEntity, SelectEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSelectEntityDescription

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: WallboxSelectEntityDescription,
    ) -> None:
        """Initialize a Wallbox select entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def current_option(self) -> str | None:
        """Return an option."""
        return self.entity_description.current_option_fn(self.coordinator)

    async def async_select_option(self, option: str) -> None:
        """Handle the selection of an option."""
        try:
            await self.entity_description.select_option_fn(self.coordinator, option)
        except ConnectionError as e:
            raise HomeAssistantError(
                translation_key="api_failed", translation_domain=DOMAIN
            ) from e
        await self.coordinator.async_request_refresh()
