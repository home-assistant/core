"""Select entities for a pipeline."""

from __future__ import annotations

from collections.abc import Iterable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import collection, entity_registry as er, restore_state

from .const import OPTION_PREFERRED
from .pipeline import KEY_ASSIST_PIPELINE, AssistDevice
from .vad import VadSensitivity


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

    pipeline_store = hass.data[KEY_ASSIST_PIPELINE].pipeline_store
    return next(
        (item.id for item in pipeline_store.async_items() if item.name == state.state),
        None,
    )


@callback
def get_vad_sensitivity(
    hass: HomeAssistant, domain: str, unique_id_prefix: str
) -> VadSensitivity:
    """Get the chosen vad sensitivity for a domain."""
    ent_reg = er.async_get(hass)
    sensitivity_entity_id = ent_reg.async_get_entity_id(
        Platform.SELECT, domain, f"{unique_id_prefix}-vad_sensitivity"
    )
    if sensitivity_entity_id is None:
        return VadSensitivity.DEFAULT

    state = hass.states.get(sensitivity_entity_id)
    if state is None:
        return VadSensitivity.DEFAULT

    return VadSensitivity(state.state)


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

    def __init__(self, hass: HomeAssistant, domain: str, unique_id_prefix: str) -> None:
        """Initialize a pipeline selector."""
        self._domain = domain
        self._unique_id_prefix = unique_id_prefix
        self._attr_unique_id = f"{unique_id_prefix}-pipeline"
        self.hass = hass
        self._update_options()

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        pipeline_data = self.hass.data[KEY_ASSIST_PIPELINE]
        pipeline_store = pipeline_data.pipeline_store
        self.async_on_remove(
            pipeline_store.async_add_change_set_listener(self._pipelines_updated)
        )

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            self._attr_current_option = state.state

        if self.registry_entry and (device_id := self.registry_entry.device_id):
            pipeline_data.pipeline_devices[device_id] = AssistDevice(
                self._domain, self._unique_id_prefix
            )

            def cleanup() -> None:
                """Clean up registered device."""
                pipeline_data.pipeline_devices.pop(device_id)

            self.async_on_remove(cleanup)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()

    async def _pipelines_updated(
        self, change_set: Iterable[collection.CollectionChange]
    ) -> None:
        """Handle pipeline update."""
        self._update_options()
        self.async_write_ha_state()

    @callback
    def _update_options(self) -> None:
        """Handle pipeline update."""
        pipeline_store = self.hass.data[KEY_ASSIST_PIPELINE].pipeline_store
        options = [OPTION_PREFERRED]
        options.extend(sorted(item.name for item in pipeline_store.async_items()))
        self._attr_options = options

        if self._attr_current_option not in options:
            self._attr_current_option = OPTION_PREFERRED


class VadSensitivitySelect(SelectEntity, restore_state.RestoreEntity):
    """Entity to represent VAD sensitivity."""

    entity_description = SelectEntityDescription(
        key="vad_sensitivity",
        translation_key="vad_sensitivity",
        entity_category=EntityCategory.CONFIG,
    )
    _attr_should_poll = False
    _attr_current_option = VadSensitivity.DEFAULT.value
    _attr_options = [vs.value for vs in VadSensitivity]

    def __init__(self, hass: HomeAssistant, unique_id_prefix: str) -> None:
        """Initialize a pipeline selector."""
        self._attr_unique_id = f"{unique_id_prefix}-vad_sensitivity"
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is not None and state.state in self.options:
            self._attr_current_option = state.state

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self.async_write_ha_state()
