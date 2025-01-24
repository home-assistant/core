"""Support for StarLine switch."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="ign",
        translation_key="engine",
    ),
    SwitchEntityDescription(
        key="webasto",
        translation_key="webasto",
    ),
    SwitchEntityDescription(
        key="out",
        translation_key="additional_channel",
    ),
    SwitchEntityDescription(
        key="valet",
        translation_key="service_mode",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the StarLine switch."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = [
        switch
        for device in account.api.devices.values()
        if device.support_state
        for description in SWITCH_TYPES
        if (switch := StarlineSwitch(account, device, description)).is_on is not None
    ]
    async_add_entities(entities)


class StarlineSwitch(StarlineEntity, SwitchEntity):
    """Representation of a StarLine switch."""

    _attr_assumed_state = True

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(account, device, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self._device.online

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the switch."""
        if self._key == "ign":
            # Deprecated and should be removed in 2025.8
            return self._account.engine_attrs(self._device)
        return None

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._device.car_state.get(self._key)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._account.api.set_car_state(self._device.device_id, self._key, True)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._account.api.set_car_state(self._device.device_id, self._key, False)
