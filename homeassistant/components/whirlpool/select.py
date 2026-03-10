"""The select platform for Whirlpool Appliances."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from whirlpool.appliance import Appliance

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .const import DOMAIN
from .entity import WhirlpoolEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class WhirlpoolSelectDescription(SelectEntityDescription):
    """Class describing Whirlpool select entities."""

    value_fn: Callable[[Appliance], str | None]
    set_fn: Callable[[Appliance, str], Awaitable[bool]]


REFRIGERATOR_DESCRIPTIONS: Final[tuple[WhirlpoolSelectDescription, ...]] = (
    WhirlpoolSelectDescription(
        key="refrigerator_temperature_level",
        translation_key="refrigerator_temperature_level",
        options=["-4", "-2", "0", "3", "5"],
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda fridge: (
            str(val) if (val := fridge.get_offset_temp()) is not None else None
        ),
        set_fn=lambda fridge, option: fridge.set_offset_temp(int(option)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the select platform."""
    appliances_manager = config_entry.runtime_data

    async_add_entities(
        WhirlpoolSelectEntity(refrigerator, description)
        for refrigerator in appliances_manager.refrigerators
        for description in REFRIGERATOR_DESCRIPTIONS
    )


class WhirlpoolSelectEntity(WhirlpoolEntity, SelectEntity):
    """Whirlpool select entity."""

    def __init__(
        self, appliance: Appliance, description: WhirlpoolSelectDescription
    ) -> None:
        """Initialize the select entity."""
        super().__init__(appliance, unique_id_suffix=f"-{description.key}")
        self.entity_description: WhirlpoolSelectDescription = description

    @override
    @property
    def current_option(self) -> str | None:
        """Retrieve currently selected option."""
        return self.entity_description.value_fn(self._appliance)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the selected option."""
        try:
            WhirlpoolSelectEntity._check_service_request(
                await self.entity_description.set_fn(self._appliance, option)
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value_set",
            ) from err
