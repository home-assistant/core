"""Support for StarLine switch."""
from homeassistant.components.switch import SwitchEntity

from .account import StarlineAccount, StarlineDevice
from .const import DOMAIN
from .entity import StarlineEntity

SWITCH_TYPES = {
    "ign": ["Engine", "mdi:engine-outline", "mdi:engine-off-outline"],
    "webasto": ["Webasto", "mdi:radiator", "mdi:radiator-off"],
    "out": [
        "Additional Channel",
        "mdi:access-point-network",
        "mdi:access-point-network-off",
    ],
    "poke": ["Horn", "mdi:bullhorn-outline", "mdi:bullhorn-outline"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine switch."""
    account: StarlineAccount = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for device in account.api.devices.values():
        if device.support_state:
            for key, value in SWITCH_TYPES.items():
                switch = StarlineSwitch(account, device, key, *value)
                if switch.is_on is not None:
                    entities.append(switch)
    async_add_entities(entities)


class StarlineSwitch(StarlineEntity, SwitchEntity):
    """Representation of a StarLine switch."""

    def __init__(
        self,
        account: StarlineAccount,
        device: StarlineDevice,
        key: str,
        name: str,
        icon_on: str,
        icon_off: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(account, device, key, name)
        self._icon_on = icon_on
        self._icon_off = icon_off

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
        return self._icon_on if self.is_on else self._icon_off

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
