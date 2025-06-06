"""Select entities for Seko Pooldose API.

Entities are enabled by default unless otherwise specified in the mapping.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import SELECT_MAP, SELECT_OPTION_CONVERSION, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose select entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities = [
        PooldoseSelect(
            coordinator=coordinator,
            api=api,
            translation_key=translation_key,
            uid=uid,
            key=key,
            options=options,
            serialnumber=serialnumber,
            entity_category=entity_category,
            device_info_dict=device_info_dict,
            enabled_by_default=enabled_by_default,
        )
        for uid, (
            translation_key,
            key,
            options,
            entity_category,
            enabled_by_default,
        ) in SELECT_MAP.items()
    ]
    async_add_entities(entities)


class PooldoseSelect(CoordinatorEntity, SelectEntity):
    """Select entity for controlling Seko Pooldose API select options."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        api: Any,
        translation_key: str,
        uid: str,
        key: str,
        options: list[tuple[int, str]],
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize the PooldoseSelect entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._raw_options = options
        self._options_map = {str(val): label for val, label in options}
        self._reverse_map = {label: str(val) for val, label in options}
        self._attr_entity_category = entity_category
        self._attr_device_info = device_info(device_info_dict)
        self._attr_entity_registry_enabled_default = enabled_by_default

        # Use conversion table for user-friendly labels
        self._conversion = SELECT_OPTION_CONVERSION.get(uid, {})

    @property
    def options(self) -> list[str]:
        """Return the list of user-friendly options."""
        return [self._conversion.get(label, label) for _, label in self._raw_options]

    @property
    def current_option(self) -> str | None:
        """Return the current user-friendly option."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][self._key]
            if isinstance(value, dict) and "current" in value:
                current_val = str(value["current"])
                label = self._options_map.get(current_val)
                return self._conversion.get(label, label) if label else None
            if isinstance(value, int):
                label = self._options_map.get(str(value))
                return self._conversion.get(label, label) if label else None
            else:  # noqa: RET505
                return None
        except (KeyError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Find the internal label for the user-friendly option
        label = next(
            (lbl for lbl in self._conversion if self._conversion[lbl] == option),
            option,
        )
        for val, lbl in self._raw_options:
            if lbl == label:
                await self._api.set_value(self._key, int(val), "NUMBER")
                break
