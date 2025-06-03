"""The Seko Pooldose API Switches."""

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

SWITCHES = {
    "pool_dosierung_aussetzen": [
        "Dosierung stoppen",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
        "F",
        "O",
    ]
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pooldose switch entities from a config entry."""
    data = hass.data["pooldose"][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    entities = []
    for uid, (name, key, off_val, on_val) in SWITCHES.items():
        entities.append(
            PooldoseSwitch(coordinator, api, name, uid, key, off_val, on_val)
        )
    async_add_entities(entities)


class PooldoseSwitch(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling Seko Pooldose API switches."""

    def __init__(self, coordinator, api, name, uid, key, off_val, on_val) -> None:
        """Initialize the PooldoseSwitch entity.

        Args:
            coordinator: The data update coordinator.
            api: The API instance for communication.
            name: The display name of the switch.
            uid: The unique ID for the switch entity.
            key: The key used to identify the switch in the API.
            off_val: The value to set for turning off the switch.
            on_val: The value to set for turning on the switch.

        """
        super().__init__(coordinator)
        self._api = api
        self._attr_name = name
        self._attr_unique_id = uid
        self._key = key
        self._off_val = off_val
        self._on_val = on_val

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
        """Return True if the switch is on, False if off, or None if unknown."""
        values = self.coordinator.data
        try:
            value = values["devicedata"][self._api.serial_key][self._key]
            return bool(value) if isinstance(value, (bool, str)) else None
        except (KeyError, TypeError):
            return None
