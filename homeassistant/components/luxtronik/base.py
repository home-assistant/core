"""Luxtronik Home Assistant Base Device Model."""
# region Imports
from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import get_sensor_data
from .const import ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY, DeviceKey
from .coordinator import LuxtronikCoordinator
from .model import LuxtronikEntityDescription

# endregion Imports


class LuxtronikEntity(CoordinatorEntity[LuxtronikCoordinator]):
    """Luxtronik base device."""

    entity_description: LuxtronikEntityDescription

    def __init__(
        self,
        coordinator: LuxtronikCoordinator,
        description: LuxtronikEntityDescription,
        device_info_ident: DeviceKey,
        platform: Platform,
    ) -> None:
        """Init LuxtronikEntity."""
        super().__init__(coordinator=coordinator)
        self._attr_extra_state_attributes = {
            ATTR_EXTRA_STATE_ATTRIBUTE_LUXTRONIK_KEY: f"{description.luxtronik_key.name[1:5]} {description.luxtronik_key.value}"
        }
        for field in description.__dataclass_fields__:
            if field.startswith("luxtronik_key_"):
                value = description.__getattribute__(field)
                if value is not None:
                    self._attr_extra_state_attributes[
                        field
                    ] = f"{value.name[1:5]} {value.value}"
        if description.translation_key is None:
            description.translation_key = description.key
        if description.entity_registry_enabled_default:
            description.entity_registry_enabled_default = coordinator.entity_visible(
                description
            )
        self.entity_description = description
        self._attr_device_info = coordinator.device_infos[device_info_ident.value]

        translation_key = (
            description.key
            if description.translation_key_name is None
            else description.translation_key_name
        )
        self._attr_name = coordinator.get_device_entity_title(translation_key, platform)
        self._attr_state = get_sensor_data(
            coordinator.data, description.luxtronik_key.value
        )

    @property
    def icon(self) -> str | None:
        """Return the icon to be used for this entity."""
        if self.entity_description.icon_by_state is not None:
            if self._attr_state in self.entity_description.icon_by_state:
                return self.entity_description.icon_by_state.get(str(self._attr_state))
            return None
        return super().icon

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_state = get_sensor_data(
            self.coordinator.data, self.entity_description.luxtronik_key.value
        )
        super()._handle_coordinator_update()
