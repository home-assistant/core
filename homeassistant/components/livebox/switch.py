"""Sensor for Livebox router."""
import logging

from homeassistant.components.switch import SwitchDevice

from .const import COORDINATOR, DOMAIN, LIVEBOX_API, LIVEBOX_ID, TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""
    datas = hass.data[DOMAIN][config_entry.entry_id]
    box_id = datas[LIVEBOX_ID]
    api = datas[LIVEBOX_API]
    coordinator = datas[COORDINATOR]
    async_add_entities([WifiSwitch(coordinator, box_id, api)], True)


class WifiSwitch(SwitchDevice):
    """Representation of a livebox sensor."""

    def __init__(self, coordinator, box_id, api):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self.box_id = box_id
        self._api = api

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Wifi switch"

    @property
    def unique_id(self):
        """Return unique_id."""
        return f"{self.box_id}_wifi"

    @property
    def device_info(self):
        """Return the device info."""

        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": TEMPLATE_SENSOR,
            "via_device": (DOMAIN, self.box_id),
        }

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.coordinator.data.get("wifi")

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """When entity will be removed from hass."""
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    async def async_update(self) -> None:
        """Update WLED entity."""
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        parameters = {"Enable": "true", "Status": "true"}
        await self._api.async_set_wifi(parameters)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        parameters = {"Enable": "false", "Status": "false"}
        await self._api.async_set_wifi(parameters)
