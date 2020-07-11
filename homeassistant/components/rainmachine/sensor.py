"""This platform provides support for sensor data from RainMachine."""
import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import RainMachineEntity
from .const import (
    DATA_CLIENT,
    DATA_PROVISION_SETTINGS,
    DATA_RESTRICTIONS_UNIVERSAL,
    DOMAIN as RAINMACHINE_DOMAIN,
    SENSOR_UPDATE_TOPIC,
)

_LOGGER = logging.getLogger(__name__)

TYPE_FLOW_SENSOR_CLICK_M3 = "flow_sensor_clicks_cubic_meter"
TYPE_FLOW_SENSOR_CONSUMED_LITERS = "flow_sensor_consumed_liters"
TYPE_FLOW_SENSOR_START_INDEX = "flow_sensor_start_index"
TYPE_FLOW_SENSOR_WATERING_CLICKS = "flow_sensor_watering_clicks"
TYPE_FREEZE_TEMP = "freeze_protect_temp"

SENSORS = {
    TYPE_FLOW_SENSOR_CLICK_M3: (
        "Flow Sensor Clicks",
        "mdi:water-pump",
        "clicks/m^3",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_CONSUMED_LITERS: (
        "Flow Sensor Consumed Liters",
        "mdi:water-pump",
        "liter",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_START_INDEX: (
        "Flow Sensor Start Index",
        "mdi:water-pump",
        "index",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_WATERING_CLICKS: (
        "Flow Sensor Clicks",
        "mdi:water-pump",
        "clicks",
        None,
        False,
        DATA_PROVISION_SETTINGS,
    ),
    TYPE_FREEZE_TEMP: (
        "Freeze Protect Temperature",
        "mdi:thermometer",
        TEMP_CELSIUS,
        "temperature",
        True,
        DATA_RESTRICTIONS_UNIVERSAL,
    ),
}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up RainMachine sensors based on a config entry."""
    rainmachine = hass.data[RAINMACHINE_DOMAIN][DATA_CLIENT][entry.entry_id]
    async_add_entities(
        [
            RainMachineSensor(
                rainmachine,
                sensor_type,
                name,
                icon,
                unit,
                device_class,
                enabled_by_default,
                api_category,
            )
            for (
                sensor_type,
                (name, icon, unit, device_class, enabled_by_default, api_category),
            ) in SENSORS.items()
        ]
    )


class RainMachineSensor(RainMachineEntity):
    """A sensor implementation for raincloud device."""

    def __init__(
        self,
        rainmachine,
        sensor_type,
        name,
        icon,
        unit,
        device_class,
        enabled_by_default,
        api_category,
    ):
        """Initialize."""
        super().__init__(rainmachine)

        self._api_category = api_category
        self._device_class = device_class
        self._enabled_by_default = enabled_by_default
        self._icon = icon
        self._name = name
        self._sensor_type = sensor_type
        self._state = None
        self._unit = unit

    @property
    def entity_registry_enabled_default(self):
        """Determine whether an entity is enabled by default."""
        return self._enabled_by_default

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def state(self) -> str:
        """Return the name of the entity."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "{}_{}".format(
            self.rainmachine.device_mac.replace(":", ""), self._sensor_type
        )

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

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
        """Update the sensor's state."""
        if self._sensor_type == TYPE_FLOW_SENSOR_CLICK_M3:
            self._state = self.rainmachine.data[DATA_PROVISION_SETTINGS]["system"].get(
                "flowSensorClicksPerCubicMeter"
            )
        elif self._sensor_type == TYPE_FLOW_SENSOR_CONSUMED_LITERS:
            clicks = self.rainmachine.data[DATA_PROVISION_SETTINGS]["system"].get(
                "flowSensorWateringClicks"
            )
            clicks_per_m3 = self.rainmachine.data[DATA_PROVISION_SETTINGS][
                "system"
            ].get("flowSensorClicksPerCubicMeter")

            if clicks and clicks_per_m3:
                self._state = (clicks * 1000) / clicks_per_m3
            else:
                self._state = None
        elif self._sensor_type == TYPE_FLOW_SENSOR_START_INDEX:
            self._state = self.rainmachine.data[DATA_PROVISION_SETTINGS]["system"].get(
                "flowSensorStartIndex"
            )
        elif self._sensor_type == TYPE_FLOW_SENSOR_WATERING_CLICKS:
            self._state = self.rainmachine.data[DATA_PROVISION_SETTINGS]["system"].get(
                "flowSensorWateringClicks"
            )
        elif self._sensor_type == TYPE_FREEZE_TEMP:
            self._state = self.rainmachine.data[DATA_RESTRICTIONS_UNIVERSAL][
                "freezeProtectTemp"
            ]
