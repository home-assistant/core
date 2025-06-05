"""Switch platform for Seko Pooldose."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import SWITCHES, device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose switch entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    serialnumber = entry.data["serialnumber"]
    device_info_dict = data.get("device_info", {})

    entities = [
        PooldoseSwitch(
            coordinator=coordinator,
            api=api,
            translation_key=translation_key,
            uid=uid,
            key=key,
            off_val=off_val,
            on_val=on_val,
            serialnumber=serialnumber,
            entity_category=entity_category,
            device_class=SwitchDeviceClass(device_class) if device_class else None,
            device_info_dict=device_info_dict,
        )
        for uid, (
            translation_key,
            key,
            off_val,
            on_val,
            entity_category,
            device_class,
        ) in SWITCHES.items()
    ]
    async_add_entities(entities)


class PooldoseSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling Seko Pooldose API switches."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        api: Any,
        translation_key: str,
        uid: str,
        key: str,
        off_val: Any,
        on_val: Any,
        serialnumber: str,
        entity_category: EntityCategory | None,
        device_class: SwitchDeviceClass | None,
        device_info_dict: dict[str, Any],
    ) -> None:
        """Initialize the PooldoseSwitch entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{serialnumber}_{key}"
        self._key = key
        self._off_val = off_val
        self._on_val = on_val
        self._attr_entity_category = entity_category
        self._attr_device_class = device_class
        self._attr_device_info = device_info(device_info_dict)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._api.set_value(self._key, self._on_val)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._api.set_value(self._key, self._off_val)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool | None:
        """Return True if the switch is on, None if unknown."""
        try:
            value = self.coordinator.data["devicedata"][self._api.serial_key][self._key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value == self._on_val
            else:  # noqa: RET505
                return None
        except (KeyError, TypeError):
            return None
