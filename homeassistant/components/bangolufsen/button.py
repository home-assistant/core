"""Button entities for the Bang & Olufsen integration."""


from __future__ import annotations

from mozart_api.models import Preset

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, BangOlufsenEntity, EntityEnum, generate_favourite_attributes
from .coordinator import BangOlufsenCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Button entities from config entry."""
    entities = []
    configuration = hass.data[DOMAIN][config_entry.unique_id]

    # Add Button entities.
    for button in configuration[EntityEnum.FAVOURITES]:
        entities.append(button)

    async_add_entities(new_entities=entities)


class BangOlufsenButton(ButtonEntity, BangOlufsenEntity):
    """Base Button class."""


class BangOlufsenButtonFavourite(CoordinatorEntity, BangOlufsenButton):
    """Favourite Button."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: BangOlufsenCoordinator,
        favourite: Preset,
    ) -> None:
        """Init a favourite Button."""
        CoordinatorEntity.__init__(self, coordinator)
        BangOlufsenButton.__init__(self, entry)

        self._favourite_id: int = int(favourite.name[6:])
        self._favourite: Preset = favourite
        self._attr_name = f"{self._name} Favourite {self._favourite_id}"

        self._attr_unique_id = f"{self._unique_id}-favourite-{self._favourite_id}"

        if self._favourite_id in range(10):
            self._attr_icon = f"mdi:numeric-{self._favourite_id}-box"
        else:
            self._attr_icon = "mdi:numeric-9-plus-box"

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self.async_on_remove(
            self.coordinator.async_add_listener(self._update_favourite)
        )

        self._attr_extra_state_attributes = generate_favourite_attributes(
            self._favourite
        )

    async def async_press(self) -> None:
        """Handle the action."""
        self._client.activate_preset(id=self._favourite_id, async_req=True)

    @callback
    def _update_favourite(self) -> None:
        """Update favourite attribute."""
        old_favourite = self._favourite
        self._favourite = self.coordinator.data["favourites"][str(self._favourite_id)]

        # Only update if there is something to update
        if old_favourite != self._favourite:
            self._attr_extra_state_attributes = generate_favourite_attributes(
                self._favourite
            )

            self.async_write_ha_state()
