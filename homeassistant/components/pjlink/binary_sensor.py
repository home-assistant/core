"""Binary sensor entities for PJLink integration."""

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_IS_WARNING, DOMAIN, ERROR_KEYS
from .coordinator import PJLinkUpdateCoordinator
from .entity import PJLinkEntity

LAMP_STATE_SENSOR = BinarySensorEntityDescription(
    key="lamp_state",
    name="Lamp State",
    entity_category=EntityCategory.DIAGNOSTIC,
    device_class=BinarySensorDeviceClass.RUNNING,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up PJLink from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: PJLinkUpdateCoordinator = domain_data[entry.entry_id]

    entities: list[PJLinkEntity] = []

    # Create lamp entities
    for lamp_idx in range(coordinator.device.lamp_count):
        entities.append(
            PJLinkLampBinarySensorEntity(coordinator=coordinator, lamp_idx=lamp_idx)
        )

    # Create error entities
    for error_key, friendly_name in ERROR_KEYS:
        entities.append(
            PJLinkErrorBinarySensorEntity(
                coordinator=coordinator,
                error_key=error_key,
                friendly_name=friendly_name,
            )
        )

    async_add_entities(entities)


class PJLinkErrorBinarySensorEntity(PJLinkEntity, BinarySensorEntity):
    """PJLink device error state binary sensor."""

    _attr_has_entity_name = True

    _attr_is_warning = False

    def __init__(
        self, coordinator: PJLinkUpdateCoordinator, error_key: str, friendly_name: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        description = BinarySensorEntityDescription(
            key=f"{error_key}_error_state",
            name=friendly_name,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.PROBLEM,
        )

        self.error_name = error_key

        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.projector_unique_id}_{description.key}"

        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        error_state = self.device.async_get_error_state(self.error_name)

        self._attr_is_on = error_state != "ok"
        self._attr_is_warning = error_state == "warning"

    @property
    def is_warning(self) -> bool:
        """Get whether the error is a warning."""
        return self._attr_is_warning

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Add the extra projector specific attributes."""
        return {ATTR_IS_WARNING: self.is_warning}


class PJLinkLampBinarySensorEntity(PJLinkEntity, BinarySensorEntity):
    """PJLink lamp state binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PJLinkUpdateCoordinator, lamp_idx: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        description = LAMP_STATE_SENSOR

        self.lamp_index = lamp_idx

        self.entity_description = description
        self._attr_name = description.name
        self._attr_unique_id = f"{coordinator.name}_lamp_{lamp_idx}_state"
        self._async_update_attrs()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle coordinator updates."""
        self._attr_is_on = self.device.async_get_lamp_state(self.lamp_index)["state"]
