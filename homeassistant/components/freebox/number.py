"""Support for Freebox Delta, Revolution and Mini 4K."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from freebox_api.exceptions import InsufficientPermissionsError

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .router import FreeboxRouter


@dataclass
class FreeboxNumberSetValueMixin:
    """Mixin for required keys."""

    async_set_value: Callable[[FreeboxRouter, int], Awaitable]


@dataclass
class FreeboxNumberEntityDescription(
    NumberEntityDescription, FreeboxNumberSetValueMixin
):
    """Class describing Freebox number entities."""


NUMBER_DESCRIPTIONS: tuple[FreeboxNumberEntityDescription, ...] = (
    FreeboxNumberEntityDescription(
        key="lcd_brightness",
        icon="mdi:monitor",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        mode=NumberMode.SLIDER,
        async_set_value=lambda router, value: router.set_brightness(brightness=value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the number."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    async_add_entities(
        [
            FreeboxLCDNumber(router, entity_description)
            for entity_description in NUMBER_DESCRIPTIONS
        ],
        True,
    )


class FreeboxNumber(NumberEntity):
    """Representation of a Freebox number entity."""

    _attr_has_entity_name = True
    entity_description: FreeboxNumberEntityDescription

    @property
    def translation_key(self) -> str | None:
        """Get translation string of Number from entity key."""
        return self.entity_description.key

    def __init__(
        self,
        router: FreeboxRouter,
        entity_description: FreeboxNumberEntityDescription,
    ) -> None:
        """Initialize the switch."""
        self.entity_description = entity_description
        self._attr_unique_id = f"{router.mac}-{entity_description.key}"
        self._attr_device_info = router.device_info
        self._router = router

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        await self.entity_description.async_set_value(self._router, int(value))


class FreeboxLCDNumber(FreeboxNumber):
    """Representation of a Freebox number entity."""

    @callback
    def async_update_state(self) -> None:
        """Update the Freebox sensor."""
        self._attr_native_value = self._router.lcd_settings.get(
            self.entity_description.key
        )

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_lcd_update,
                self.async_on_demand_update,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value of the entity."""
        try:
            await super().async_set_native_value(value)

            self._router.lcd_settings[self.entity_description.key] = int(value)

            self.async_update_state()
            self.async_write_ha_state()
        except InsufficientPermissionsError:
            self.async_on_demand_update()

            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id="missing_lcd_permission",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_lcd_permission",
            )
