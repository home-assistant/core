"""Sensor entity exposing the status of a selected Mistral model."""

from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_models_coordinator
from .api import SUBENTRY_TYPES
from .const import (
    CONF_CHAT_MODEL,
    DEFAULT_MODEL_BY_TYPE,
    DOMAIN,
    RECOMMENDED_CHAT_MODEL,
)
from .coordinator import MistralModelsCoordinator

if TYPE_CHECKING:
    from . import MistralAIConfigEntry

PARALLEL_UPDATES = 0

_ICONS = {
    "active": "mdi:check-circle",
    "deprecated": "mdi:alert-circle",
    "unknown": "mdi:help-circle",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral sensor platform."""
    coordinator = get_models_coordinator(hass, config_entry)
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type not in SUBENTRY_TYPES:
            continue

        async_add_entities(
            [MistralModelStatusSensor(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralModelStatusSensor(
    CoordinatorEntity[MistralModelsCoordinator], SensorEntity
):
    """Sensor showing the deprecation status of a selected model."""

    _attr_has_entity_name = True
    _attr_name = "Model status"

    def __init__(
        self,
        coordinator: MistralModelsCoordinator,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_model_status"
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
        )

    @property
    def _model_id(self) -> str:
        default = DEFAULT_MODEL_BY_TYPE.get(
            self.subentry.subentry_type, RECOMMENDED_CHAT_MODEL
        )
        return self.subentry.data.get(CONF_CHAT_MODEL, default)

    @property
    @override
    def native_value(self) -> str | None:
        return self.coordinator.model_status(self._model_id).get("status")

    @property
    @override
    def icon(self) -> str | None:
        if self.native_value is None:
            return _ICONS["unknown"]
        return _ICONS.get(self.native_value, _ICONS["unknown"])

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | None]:
        data = self.coordinator.model_status(self._model_id)
        return {
            "model": data.get("id"),
            "deprecation": data.get("deprecation"),
            "deprecation_replacement_model": data.get("deprecation_replacement_model"),
        }
