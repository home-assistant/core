"""Sensor for Livebox router."""
import logging

from homeassistant.helpers.entity import Entity

from .const import ATTR_SENSORS, COORDINATOR, DOMAIN, LIVEBOX_ID, TEMPLATE_SENSOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the sensors."""
    datas = hass.data[DOMAIN][config_entry.entry_id]
    box_id = datas[LIVEBOX_ID]
    coordinator = datas[COORDINATOR]
    nmc = coordinator.data["nmc"]
    if "ETHERNET" not in nmc["WanMode"].upper():
        async_add_entities(
            [
                FlowSensor(coordinator, box_id, "down"),
                FlowSensor(coordinator, box_id, "up"),
            ],
            True,
        )


class FlowSensor(Entity):
    """Representation of a livebox sensor."""

    unit_of_measurement = "Mb/s"

    def __init__(self, coordinator, box_id, flow_direction):
        """Initialize the sensor."""
        self.box_id = box_id
        self.coordinator = coordinator
        self._attributs = ATTR_SENSORS[flow_direction]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attributs["name"]

    @property
    def unique_id(self):
        """Return unique_id."""
        cr = self._attributs["current_rate"]
        return f"{self.box_id}_{cr}"

    @property
    def state(self):
        """Return the state of the device."""
        if self.coordinator.data["dsl_status"].get(self._attributs["current_rate"]):
            return round(
                self.coordinator.data["dsl_status"][self._attributs["current_rate"]]
                / 1000,
                2,
            )
        return None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

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
    def device_state_attributes(self):
        """Return the device state attributes."""
        _attributs = {}
        for key, value in self._attributs["attr"].items():
            _attributs[key] = self.coordinator.data["dsl_status"].get(value)
        return _attributs

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
