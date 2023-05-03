"""Fully Kiosk Browser number entity."""
from __future__ import annotations

from contextlib import suppress

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator
from .entity import FullyKioskEntity

ENTITY_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="timeToScreensaverV2",
        name="Screensaver timer",
        native_max_value=9999,
        native_step=1,
        native_min_value=0,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="screensaverBrightness",
        name="Screensaver brightness",
        native_max_value=255,
        native_step=1,
        native_min_value=0,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="timeToScreenOffV2",
        name="Screen off timer",
        native_max_value=9999,
        native_step=1,
        native_min_value=0,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key="screenBrightness",
        name="Screen brightness",
        native_max_value=255,
        native_step=1,
        native_min_value=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fully Kiosk Browser number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FullyNumberEntity(coordinator, entity)
        for entity in ENTITY_TYPES
        if entity.key in coordinator.data["settings"]
    )


class FullyNumberEntity(FullyKioskEntity, NumberEntity):
    """Representation of a Fully Kiosk Browser entity."""

    def __init__(
        self,
        coordinator: FullyKioskDataUpdateCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data['deviceID']}-{description.key}"

    @property
    def native_value(self) -> int | None:
        """Return the state of the number entity."""
        if (
            value := self.coordinator.data["settings"].get(self.entity_description.key)
        ) is None:
            return None

        with suppress(ValueError):
            return int(value)

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        await self.coordinator.fully.setConfigurationString(
            self.entity_description.key, int(value)
        )
