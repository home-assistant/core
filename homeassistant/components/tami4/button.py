"""Button entities for Tami4Edge."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from Tami4EdgeAPI import Tami4EdgeAPI

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import API, DOMAIN
from .entity import Tami4EdgeBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Tami4EdgeButtonEntityDescription(ButtonEntityDescription):
    """A class that describes Tami4Edge button entities."""

    press_fn: Callable[[Tami4EdgeAPI], None]


BOIL_WATER_BUTTON = Tami4EdgeButtonEntityDescription(
    key="boil_water",
    translation_key="boil_water",
    press_fn=lambda api: api.boil_water(),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Perform the setup for Tami4Edge."""

    api: Tami4EdgeAPI = hass.data[DOMAIN][entry.entry_id][API]
    device = await hass.async_add_executor_job(api.get_device)
    drinks = device.drinks

    buttons = [
        Tami4EdgeButton(
            api=api,
            entity_description=Tami4EdgeButtonEntityDescription(
                key=drink.id,
                name=drink.name,
                press_fn=lambda api, drink=drink: api.prepare_drink(drink),  # type: ignore[misc]
            ),
        )
        for drink in drinks
    ]

    buttons.append(Tami4EdgeButton(api, BOIL_WATER_BUTTON))
    async_add_entities(buttons)


class Tami4EdgeButton(Tami4EdgeBaseEntity, ButtonEntity):
    """Button entity for Tami4Edge."""

    entity_description: Tami4EdgeButtonEntityDescription

    def press(self) -> None:
        """Handle the button press."""
        self.entity_description.press_fn(self._api)
