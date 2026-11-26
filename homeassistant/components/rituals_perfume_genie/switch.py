"""Support for Rituals Perfume Genie switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from ritualsgenie import RitualsGenie, RitualsGenieHub

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry, RitualsHubsCoordinator
from .entity import DiffuserEntity, async_add_diffusers, rituals_action

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RitualsSwitchEntityDescription(SwitchEntityDescription):
    """Class describing Rituals switch entities."""

    has_fn: Callable[[RitualsGenieHub], bool] = lambda _: True
    is_on_fn: Callable[[RitualsGenieHub], bool | None]
    turn_on_fn: Callable[[RitualsGenie, str], Awaitable[None]]
    turn_off_fn: Callable[[RitualsGenie, str], Awaitable[None]]


ENTITY_DESCRIPTIONS = (
    RitualsSwitchEntityDescription(
        key="is_on",
        name=None,
        translation_key="fan",
        is_on_fn=lambda hub: hub.is_on,
        turn_on_fn=lambda client, hub_hash: client.turn_on(hub_hash),
        turn_off_fn=lambda client, hub_hash: client.turn_off(hub_hash),
    ),
    RitualsSwitchEntityDescription(
        key="standby_led",
        translation_key="standby_led",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda hub: hub.supports_standby_led,
        is_on_fn=lambda hub: hub.standby_led,
        turn_on_fn=lambda client, hub_hash: client.set_standby_led(
            hub_hash, enabled=True
        ),
        turn_off_fn=lambda client, hub_hash: client.set_standby_led(
            hub_hash, enabled=False
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser switch."""
    hubs = config_entry.runtime_data.hubs

    @callback
    def add_diffusers(hublots: list[str]) -> None:
        async_add_entities(
            RitualsSwitchEntity(hubs, hublot, description)
            for hublot in hublots
            for description in ENTITY_DESCRIPTIONS
            if description.has_fn(hubs.data[hublot])
        )

    async_add_diffusers(config_entry, add_diffusers)


class RitualsSwitchEntity(DiffuserEntity, SwitchEntity):
    """Representation of a diffuser switch."""

    entity_description: RitualsSwitchEntityDescription

    def __init__(
        self,
        coordinator: RitualsHubsCoordinator,
        hublot: str,
        description: RitualsSwitchEntityDescription,
    ) -> None:
        """Initialize the diffuser switch."""
        super().__init__(coordinator, hublot, description)
        self._attr_is_on = description.is_on_fn(self.hub)

    @override
    @rituals_action
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.turn_on_fn(self.coordinator.client, self.hub.hash)
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    @rituals_action
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.turn_off_fn(
            self.coordinator.client, self.hub.hash
        )
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.hublot in self.coordinator.data:
            self._attr_is_on = self.entity_description.is_on_fn(self.hub)
        super()._handle_coordinator_update()
