"""Select entity to choose a model at runtime."""

from typing import TYPE_CHECKING, override

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import get_models_coordinator
from .api import SUBENTRY_TYPES
from .const import CONF_CHAT_MODEL
from .entity import MistralEntity

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral select platform."""
    coordinator = get_models_coordinator(hass, config_entry)
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type not in SUBENTRY_TYPES:
            continue

        async_add_entities(
            [MistralModelSelectEntity(coordinator, config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralModelSelectEntity(SelectEntity, MistralEntity):
    """Select entity to choose the Mistral model of a subentry."""

    _attr_has_entity_name = True
    _attr_name = "Model"

    def __init__(
        self,
        coordinator,
        entry: MistralAIConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(entry, subentry)
        self.coordinator = coordinator
        self._attr_unique_id = f"{subentry.subentry_id}_model"
        self._attr_options = []
        self._attr_current_option = subentry.data.get(CONF_CHAT_MODEL)

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.hass.async_create_task(self._async_refresh_options())

    async def _async_refresh_options(self) -> None:
        await self.coordinator.async_request_refresh()

        models = self.coordinator.model_ids(self.subentry.subentry_type)
        if not models:
            return

        if self._attr_current_option and self._attr_current_option not in models:
            models.append(self._attr_current_option)

        self._attr_options = models
        self.async_write_ha_state()

    @override
    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options and self._attr_options:
            return

        data = {**self.subentry.data, CONF_CHAT_MODEL: option}
        self.hass.config_entries.async_update_subentry(
            self.entry, self.subentry, data=data
        )
        self._attr_current_option = option
        self.async_write_ha_state()
        # Notify sensor/binary_sensor that the selected model changed.
        self.coordinator.async_update_listeners()
