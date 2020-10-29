"""This platform provides binary sensors for key RainMachine data."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import RainMachineEntity
from .const import (
    DATA_CLIENT,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_CURRENT,
    DATA_RESTRICTIONS_UNIVERSAL,
    DOMAIN as RAINMACHINE_DOMAIN,
    SENSOR_UPDATE_TOPIC,
)

TYPE_FLOW_SENSOR = "flow_sensor"
TYPE_FREEZE = "freeze"
TYPE_FREEZE_PROTECTION = "freeze_protection"
TYPE_HOT_DAYS = "extra_water_on_hot_days"
TYPE_HOURLY = "hourly"
TYPE_MONTH = "month"
TYPE_RAINDELAY = "raindelay"
TYPE_RAINSENSOR = "rainsensor"
TYPE_WEEKDAY = "weekday"

BINARY_SENSORS = {
    TYPE_FLOW_SENSOR: ("Flow Sensor", "mdi:water-pump", True, DATA_PROVISION_SETTINGS),
    TYPE_FREEZE: ("Freeze Restrictions", "mdi:cancel", True, DATA_RESTRICTIONS_CURRENT),
    TYPE_FREEZE_PROTECTION: (
        "Freeze Protection",
        "mdi:weather-snowy",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
    TYPE_HOT_DAYS: (
        "Extra Water on Hot Days",
        "mdi:thermometer-lines",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
    TYPE_HOURLY: (
        "Hourly Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_MONTH: ("Month Restrictions", "mdi:cancel", False, DATA_RESTRICTIONS_CURRENT),
    TYPE_RAINDELAY: (
        "Rain Delay Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_RAINSENSOR: (
        "Rain Sensor Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
    TYPE_WEEKDAY: (
        "Weekday Restrictions",
        "mdi:cancel",
        False,
        DATA_RESTRICTIONS_CURRENT,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine binary sensors based on a config entry."""
    rainmachine = hass.data[RAINMACHINE_DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            RainMachineBinarySensor(
                rainmachine, sensor_type, name, icon, enabled_by_default, api_category
            )
            for (
                sensor_type,
                (name, icon, enabled_by_default, api_category),
            ) in BINARY_SENSORS.items()
        ],
    )


class RainMachineBinarySensor(RainMachineEntity, BinarySensorEntity):
    """A sensor implementation for raincloud device."""

    def __init__(
        self, rainmachine, sensor_type, name, icon, enabled_by_default, api_category
    ):
        """Initialize the sensor."""
        super().__init__(rainmachine)

        self._api_category = api_category
        self._enabled_by_default = enabled_by_default
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None

    @property
    def entity_registry_enabled_default(self):
        """Determine whether an entity is enabled by default."""
        return self._enabled_by_default

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "{}_{}".format(
            self.rainmachine.device_mac.replace(":", ""), self._sensor_type
        )

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SENSOR_UPDATE_TOPIC, self._update_state)
        )
        await self.rainmachine.async_register_sensor_api_interest(self._api_category)
        self.update_from_latest_data()

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listeners and deregister API interest."""
        super().async_will_remove_from_hass()
        self.rainmachine.async_deregister_sensor_api_interest(self._api_category)

    @callback
    def update_from_latest_data(self):
        """Update the state."""
        if self._sensor_type == TYPE_FLOW_SENSOR:
            self._state = self.rainmachine.data[DATA_PROVISION_SETTINGS]["system"].get(
                "useFlowSensor"
            )
        elif self._sensor_type == TYPE_FREEZE:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["freeze"]
        elif self._sensor_type == TYPE_FREEZE_PROTECTION:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_UNIVERSAL][
                "freezeProtectEnabled"
            ]
        elif self._sensor_type == TYPE_HOT_DAYS:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_UNIVERSAL][
                "hotDaysExtraWatering"
            ]
        elif self._sensor_type == TYPE_HOURLY:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["hourly"]
        elif self._sensor_type == TYPE_MONTH:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["month"]
        elif self._sensor_type == TYPE_RAINDELAY:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["rainDelay"]
        elif self._sensor_type == TYPE_RAINSENSOR:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["rainSensor"]
        elif self._sensor_type == TYPE_WEEKDAY:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_CURRENT]["weekDay"]
