"""Base class for the La Marzocco entities."""

from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LmApiCoordinator


@dataclass
class LaMarzoccoEntityDescription(EntityDescription):
    """Description for all LM entities."""

    extra_attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class LaMarzoccoEntity(CoordinatorEntity[LmApiCoordinator]):
    """Common elements for all entities."""

    entity_description: LaMarzoccoEntityDescription
    _attr_has_entity_name: bool = True

    def __init__(
        self,
        coordinator: LmApiCoordinator,
        hass: HomeAssistant,
        entity_description: LaMarzoccoEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._hass = hass
        self.entity_description = entity_description
        self._lm_client = self.coordinator.data
        self._attr_unique_id = (
            f"{self._lm_client.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._lm_client.serial_number)},
            name=self._lm_client.machine_name,
            manufacturer="La Marzocco",
            model=self._lm_client.true_model_name,
            sw_version=self._lm_client.firmware_version,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes."""

        def bool_to_str(value: bool | str) -> str:
            """Convert boolean values to strings to improve display in Lovelace."""
            return str(value) if isinstance(value, bool) else value

        data = self._lm_client.current_status
        keys = self.entity_description.extra_attributes.get(self._lm_client.model_name)
        if keys is None:
            return {}

        return {key: bool_to_str(data[key]) for key in keys if key in data}
