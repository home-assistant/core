"""Support for Rituals Perfume Genie numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from ritualsgenie import Attribute, RitualsGenie, RitualsGenieHub

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RitualsConfigEntry
from .entity import DiffuserEntity, async_add_diffusers, rituals_action

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RitualsNumberEntityDescription(NumberEntityDescription):
    """Class describing Rituals number entities."""

    attribute: Attribute
    value_fn: Callable[[RitualsGenieHub], int | None]
    set_value_fn: Callable[[RitualsGenie, str, int], Awaitable[None]]


ENTITY_DESCRIPTIONS = (
    RitualsNumberEntityDescription(
        key="perfume_amount",
        translation_key="perfume_amount",
        attribute=Attribute.PERFUME_AMOUNT,
        native_min_value=1,
        native_max_value=3,
        value_fn=lambda hub: hub.perfume_amount,
        set_value_fn=lambda client, hub_hash, value: client.set_perfume_amount(
            hub_hash, value
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser numbers."""
    hubs = config_entry.runtime_data.hubs

    @callback
    def add_diffusers(hublots: list[str]) -> None:
        async_add_entities(
            RitualsNumberEntity(hubs, hublot, description)
            for hublot in hublots
            for description in ENTITY_DESCRIPTIONS
        )

    async_add_diffusers(config_entry, add_diffusers)


class RitualsNumberEntity(DiffuserEntity, NumberEntity):
    """Representation of a diffuser number entity."""

    entity_description: RitualsNumberEntityDescription

    @property
    @override
    def native_value(self) -> int | None:
        """Return the number value."""
        return self.entity_description.value_fn(self.hub)

    @override
    @rituals_action
    async def async_set_native_value(self, value: float) -> None:
        """Change to new number value."""
        if not value.is_integer():
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="perfume_amount_not_whole",
                translation_placeholders={"value": str(value)},
            )
        await self.entity_description.set_value_fn(
            self.coordinator.client, self.hub.hash, int(value)
        )

        # Keep the new value until the next update, like the device has it now.
        attribute_values = self.hub.attribute_values
        attribute_values[self.entity_description.attribute] = str(int(value))
        self.async_write_ha_state()
