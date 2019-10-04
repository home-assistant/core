"""Support for StarLine switch."""
from homeassistant.components.switch import SwitchDevice
from .api import StarlineApi, StarlineDevice
from .const import DOMAIN, LOGGER

SWITCH_TYPES = {
    "ign": ["Engine", "mdi:engine-outline", "mdi:engine-off-outline"],
    "webasto": ["Webasto", "mdi:radiator", "mdi:radiator-off"],
    "out": ["Additional Channel", "mdi:access-point-network", "mdi:access-point-network-off"],
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine switch."""

    api = hass.data[DOMAIN]
    entities = []
    for device_id, device in api.devices.items():
        for key, value in SWITCH_TYPES.items():
            # TODO: check functions array
            entities.append(StarlineSwitch(api, device, key, *value))
    async_add_entities(entities)
    return True


class StarlineSwitch(SwitchDevice):
    """Representation of a StarLine switch."""

    def __init__(self, api: StarlineApi, device: StarlineDevice, key: str, switch_name: str, icon_on: str, icon_off: str):
        """Initialize the switch."""
        self._api = api
        self._device = device
        self._key = key
        self._switch_name = switch_name
        self._icon_on = icon_on
        self._icon_off = icon_off

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return f"starline-{self._key}-{self._device.device_id}"

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._device.name} {self._switch_name}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.online

    @property
    def device_state_attributes(self):
        """Return the state attributes of the switch."""
        if self._key == "ign":
            return self._device.engine_attrs
        return None

    @property
    def icon(self):
        return self._icon_on if self.is_on else self._icon_off

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._device.car_state[self._key]

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        self._api.set_car_state(self._device.device_id, self._key, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        self._api.set_car_state(self._device.device_id, self._key, False)

    @property
    def device_info(self):
        """Return the device info."""
        return self._device.device_info

    def update(self):
        """Update state of the switch."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()
        self._api.add_update_listener(self.update)
