"""Support for StarLine switch."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity


@dataclass
class StarlineRequiredKeysMixin:
    """Mixin for required keys."""

    name_: str
    icon_on: str
    icon_off: str


@dataclass
class StarlineSwitchEntityDescription(
    SwitchEntityDescription, StarlineRequiredKeysMixin
):
    """Describes Starline switch entity."""


SWITCH_TYPES: tuple[StarlineSwitchEntityDescription, ...] = (
    StarlineSwitchEntityDescription(
        key="ign",
        name_="Engine",
        icon_on="mdi:engine-outline",
        icon_off="mdi:engine-off-outline",
    ),
    StarlineSwitchEntityDescription(
        key="webasto",
        name_="Webasto",
        icon_on="mdi:radiator",
        icon_off="mdi:radiator-off",
    ),
    StarlineSwitchEntityDescription(
        key="out",
        name_="Additional Channel",
        icon_on="mdi:access-point-network",
        icon_off="mdi:access-point-network-off",
    ),
    StarlineSwitchEntityDescription(
        key="poke",
        name_="Horn",
        icon_on="mdi:bullhorn-outline",
        icon_off="mdi:bullhorn-outline",
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

    entity_description: StarlineSwitchEntityDescription

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        description: StarlineSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(account, device, description.key, description.name_)
        self.entity_description = description

    @property
    def available(self):
        """Return True if entity is available."""
        return super().available and self._device.online

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the switch."""
        if self._key == "ign":
            return self._account.engine_attrs(self._device)
        return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return (
            self.entity_description.icon_on
            if self.is_on
            else self.entity_description.icon_off
        )

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return True if entity is on."""
        if self._key == "poke":
            return False
        return self._device.car_state.get(self._key)

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        self._account.api.set_car_state(self._device.device_id, self._key, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        if self._key == "poke":
            return
        self._account.api.set_car_state(self._device.device_id, self._key, False)
