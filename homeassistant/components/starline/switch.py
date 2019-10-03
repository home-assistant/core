"""Support for StarLine switch."""
from homeassistant.components.switch import SwitchDevice
from .api import StarlineApi, StarlineDevice
from .const import DOMAIN, LOGGER


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the StarLine switch."""

    api = hass.data[DOMAIN]
    entities = []
    for device_id, device in api.devices.items():
        # TODO: check functions array
        entities.append(StarlineSwitch(api, device))
    async_add_entities(entities)
    return True


class StarlineSwitch(SwitchDevice):
    """Representation of a StarLine switch."""

    def __init__(self, api: StarlineApi, device: StarlineDevice):
        """Initialize the switch."""
        self._api = api
        self._device = device

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the switch."""
        return f"starline-switch-{str(self._device.device_id)}"

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self._device.name} Engine"

    @property
    def device_state_attributes(self):
        """Return the state attributes of the switch."""
        return self._device.engine_attrs

    @property
    def icon(self):
        return "mdi:engine-outline" if self.is_on else "mdi:engine-off-outline"

    @property
    def assumed_state(self):
        """Return True if unable to access real state of the entity."""
        return True

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._device.car_state["ign"]

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        LOGGER.debug("%s: starting engine", self._device.name)
        self._api.set_engine_state(self._device.device_id, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        LOGGER.debug("%s: stopping engine", self._device.name)
        self._api.set_engine_state(self._device.device_id, False)

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
