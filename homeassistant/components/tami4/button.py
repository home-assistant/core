"""Button entities for Tami4Edge."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from Tami4EdgeAPI import Tami4EdgeAPI
from Tami4EdgeAPI.drink import Drink

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import API, DOMAIN
from .entity import Tami4EdgeBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Tami4EdgeButtonEntityDescription(ButtonEntityDescription):
    """A class that describes Tami4Edge button entities."""

    press_fn: Callable[[Tami4EdgeAPI], None]


@dataclass(frozen=True, kw_only=True)
class Tami4EdgeDrinkButtonEntityDescription(ButtonEntityDescription):
    """A class that describes Tami4Edge Drink button entities."""

    press_fn: Callable[[Tami4EdgeAPI, Drink], None]


BOIL_WATER_BUTTON = Tami4EdgeButtonEntityDescription(
    key="boil_water",
    translation_key="boil_water",
    press_fn=lambda api: api.boil_water(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Perform the setup for Tami4Edge."""

    api: Tami4EdgeAPI = hass.data[DOMAIN][entry.entry_id][API]
    buttons: list[Tami4EdgeBaseEntity] = [Tami4EdgeButton(api, BOIL_WATER_BUTTON)]

    device = await hass.async_add_executor_job(api.get_device)
    drinks = device.drinks

    buttons.extend(
        Tami4EdgeDrinkButton(
            api=api,
            entity_description=Tami4EdgeDrinkButtonEntityDescription(
                key=drink.id,
                translation_key="prepare_drink",
                translation_placeholders={"drink_name": drink.name},
                press_fn=lambda api, drink: api.prepare_drink(drink),
            ),
            drink=drink,
        )
        for drink in drinks
    )

    async_add_entities(buttons)


class Tami4EdgeButton(Tami4EdgeBaseEntity, ButtonEntity):
    """Button entity for Tami4Edge."""

    entity_description: Tami4EdgeButtonEntityDescription

    def press(self) -> None:
        """Handle the button press."""
        self.entity_description.press_fn(self._api)


class Tami4EdgeDrinkButton(Tami4EdgeBaseEntity, ButtonEntity):
    """Drink Button entity for Tami4Edge."""

    entity_description: Tami4EdgeDrinkButtonEntityDescription

    def __init__(
        self, api: Tami4EdgeAPI, entity_description: EntityDescription, drink: Drink
    ) -> None:
        """Initialize the drink button."""
        super().__init__(api=api, entity_description=entity_description)
        self.drink = drink

    def press(self) -> None:
        """Handle the button press."""
        self.entity_description.press_fn(self._api, self.drink)
