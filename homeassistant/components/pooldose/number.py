"""Number entities for Seko Pooldose API.

Entities are enabled by default unless otherwise specified in the mapping.
"""

from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import NUMBER_MAP, device_info
from .entity import PooldoseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose number entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities = []
    for uid, (
        translation_key,
        key,
        defaults,
        entity_category,
        device_class,
        enabled_by_default,
    ) in NUMBER_MAP.items():
        entities.append(
            PooldoseNumber(
                coordinator,
                api,
                translation_key,
                uid,
                key,
                defaults,
                serialnumber,
                entity_category,
                NumberDeviceClass(device_class) if device_class else None,
                device_info_dict,
                enabled_by_default,
            )
        )
    async_add_entities(entities)


class PooldoseNumber(PooldoseEntity, NumberEntity):
    """Number entity for Seko Pooldose API."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        api: Any,
        translation_key: str,
        uid: str,
        key: str,
        defaults: dict[str, float | str],
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_class: NumberDeviceClass | None,
        device_info_dict: dict[str, Any],
        enabled_by_default: bool = True,
    ) -> None:
        """Initialize a PooldoseNumber entity."""
        super().__init__(
            coordinator,
            api,
            translation_key,
            uid,
            key,
            serialnumber,
            device_info(device_info_dict),
            enabled_by_default,
        )
        self._attr_native_min_value = float(defaults["min"])
        self._attr_native_max_value = float(defaults["max"])
        self._attr_native_unit_of_measurement = str(defaults["unit"])
        self._attr_native_step = float(defaults["step"])
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class

    @property
    def native_value(self) -> float | int | None:
        """Return the current value of the number entity."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][
                self._key
            ]["current"]
        except (KeyError, TypeError):
            return None
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value using the API."""
        await self._api.set_value(self._key, value, "NUMBER")
        await self.coordinator.async_request_refresh()
