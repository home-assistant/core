"""Binary sensor signaling whether a selected Mistral model is deprecated."""

from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MistralAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Mistral binary sensor platform."""
    coordinator = get_models_coordinator(hass, config_entry)
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type not in SUBENTRY_TYPES:
            continue

        async_add_entities(
            [MistralModelDeprecatedBinarySensor(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class MistralModelDeprecatedBinarySensor(
    CoordinatorEntity[MistralModelsCoordinator], BinarySensorEntity
):
    """Binary sensor that is on when a selected model is deprecated."""

    _attr_has_entity_name = True
    _attr_name = "Model deprecated"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: MistralModelsCoordinator,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.subentry = subentry
        self._attr_unique_id = f"{subentry.subentry_id}_model_deprecated"
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
    def is_on(self) -> bool:
        return (
            self.coordinator.model_status(self._model_id).get("status") == "deprecated"
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str | None]:
        data = self.coordinator.model_status(self._model_id)
        return {
            "model": data.get("id"),
            "deprecation": data.get("deprecation"),
            "deprecation_replacement_model": data.get("deprecation_replacement_model"),
        }
