"""Select entities for a pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, entity_registry as er, restore_state

from .const import DOMAIN
from .pipeline import PipelineStorageCollection

OPTION_PREFERRED = "preferred"


@callback
def get_chosen_pipeline(
    hass: HomeAssistant, domain: str, unique_id_prefix: str
) -> str | None:
    """Get the chosen pipeline for a domain."""
    ent_reg = er.async_get(hass)
    pipeline_entity_id = ent_reg.async_get_entity_id(
        Platform.SELECT, domain, f"{unique_id_prefix}-pipeline"
    )
    if pipeline_entity_id is None:
        return None

    state = hass.states.get(pipeline_entity_id)
    if state is None or state.state == OPTION_PREFERRED:
        return None

    pipeline_store: PipelineStorageCollection = hass.data[DOMAIN].pipeline_store
    return next(
        (item.id for item in pipeline_store.async_items() if item.name == state.state),
        None,
    )


class AssistPipelineSelect(SelectEntity, restore_state.RestoreEntity):
    """Entity to represent a pipeline selector."""

    entity_description = SelectEntityDescription(
        key="pipeline",
        translation_key="pipeline",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option = OPTION_PREFERRED
    _attr_options = [OPTION_PREFERRED]

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a pipeline selector."""
        self._attr_unique_id = f"{unique_id_prefix}-pipeline"
        self.hass = hass
        self._update_options()

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        pipeline_store: PipelineStorageCollection = self.hass.data[
            DOMAIN
        ].pipeline_store
        pipeline_store.async_add_change_set_listener(self._pipelines_updated)

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _pipelines_updated(
        self, change_sets: Iterable[collection.CollectionChangeSet]
    ) -> None:
        """Handle pipeline update."""
        self._update_options()
        self.async_write_ha_state()

    @callback
    def _update_options(self) -> None:
        """Handle pipeline update."""
        pipeline_store: PipelineStorageCollection = self.hass.data[
            DOMAIN
        ].pipeline_store
        options = [OPTION_PREFERRED]
        options.extend(sorted(item.name for item in pipeline_store.async_items()))
        self._attr_options = options

        if self._attr_current_option not in options:
            self._attr_current_option = OPTION_PREFERRED
