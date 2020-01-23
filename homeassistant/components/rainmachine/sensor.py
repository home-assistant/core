"""This platform provides support for sensor data from RainMachine."""
import logging

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_CLIENT,
    DOMAIN as RAINMACHINE_DOMAIN,
    PROVISION_SETTINGS,
    RESTRICTIONS_UNIVERSAL,
    SENSOR_UPDATE_TOPIC,
    RainMachineEntity,
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
        PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_CONSUMED_LITERS: (
        "Flow Sensor Consumed Liters",
        "mdi:water-pump",
        "liter",
        None,
        False,
        PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_START_INDEX: (
        "Flow Sensor Start Index",
        "mdi:water-pump",
        "index",
        None,
        False,
        PROVISION_SETTINGS,
    ),
    TYPE_FLOW_SENSOR_WATERING_CLICKS: (
        "Flow Sensor Clicks",
        "mdi:water-pump",
        "clicks",
        None,
        False,
        PROVISION_SETTINGS,
    ),
    TYPE_FREEZE_TEMP: (
        "Freeze Protect Temperature",
        "mdi:thermometer",
        "°C",
        "temperature",
        True,
        RESTRICTIONS_UNIVERSAL,
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
        ],
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
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def state(self) -> str:
        """Return the name of the entity."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return "{0}_{1}".format(
            self.rainmachine.device_mac.replace(":", ""), self._sensor_type
        )

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._dispatcher_handlers.append(
            async_dispatcher_connect(self.hass, SENSOR_UPDATE_TOPIC, update)
        )
        await self.rainmachine.async_register_api_interest(self._api_category)
        await self.async_update()

    async def async_update(self):
        """Update the sensor's state."""
        if self._sensor_type == TYPE_FLOW_SENSOR_CLICK_M3:
            self._state = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "flowSensorClicksPerCubicMeter"
            )
        elif self._sensor_type == TYPE_FLOW_SENSOR_CONSUMED_LITERS:
            clicks = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "flowSensorWateringClicks"
            )
            clicks_per_m3 = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "flowSensorClicksPerCubicMeter"
            )

            if clicks and clicks_per_m3:
                self._state = (clicks * 1000) / clicks_per_m3
            else:
                self._state = None
        elif self._sensor_type == TYPE_FLOW_SENSOR_START_INDEX:
            self._state = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "flowSensorStartIndex"
            )
        elif self._sensor_type == TYPE_FLOW_SENSOR_WATERING_CLICKS:
            self._state = self.rainmachine.data[PROVISION_SETTINGS]["system"].get(
                "flowSensorWateringClicks"
            )
        elif self._sensor_type == TYPE_FREEZE_TEMP:
            self._state = self.rainmachine.data[RESTRICTIONS_UNIVERSAL][
                "freezeProtectTemp"
            ]

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listeners and deregister API interest."""
        super().async_will_remove_from_hass()
        self.rainmachine.async_deregister_api_interest(self._api_category)
