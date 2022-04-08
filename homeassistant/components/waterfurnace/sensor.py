"""Support for Waterfurnace."""
from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import PERCENTAGE, POWER_WATT, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DOMAIN as WF_DOMAIN, UPDATE_TOPIC


class WFSensorConfig:
    """Water Furnace Sensor configuration."""

    def __init__(
        self,
        friendly_name,
        field,
        icon="mdi:gauge",
        unit_of_measurement=None,
        device_class=None,
    ):
        """Initialize configuration."""
        self.device_class = device_class
        self.friendly_name = friendly_name
        self.field = field
        self.icon = icon
        self.unit_of_measurement = unit_of_measurement


SENSORS = [
    WFSensorConfig("Furnace Mode", "mode"),
    WFSensorConfig("Total Power", "totalunitpower", "mdi:flash", POWER_WATT),
    WFSensorConfig(
        "Active Setpoint",
        "tstatactivesetpoint",
        None,
        TEMP_FAHRENHEIT,
        SensorDeviceClass.TEMPERATURE,
    ),
    WFSensorConfig(
        "Leaving Air",
        "leavingairtemp",
        None,
        TEMP_FAHRENHEIT,
        SensorDeviceClass.TEMPERATURE,
    ),
    WFSensorConfig(
        "Room Temp",
        "tstatroomtemp",
        None,
        TEMP_FAHRENHEIT,
        SensorDeviceClass.TEMPERATURE,
    ),
    WFSensorConfig("Loop Temp", "enteringwatertemp", None, TEMP_FAHRENHEIT),
    WFSensorConfig(
        "Humidity Set Point", "tstathumidsetpoint", "mdi:water-percent", PERCENTAGE
    ),
    WFSensorConfig(
        "Humidity", "tstatrelativehumidity", "mdi:water-percent", PERCENTAGE
    ),
    WFSensorConfig("Compressor Power", "compressorpower", "mdi:flash", POWER_WATT),
    WFSensorConfig("Fan Power", "fanpower", "mdi:flash", POWER_WATT),
    WFSensorConfig("Aux Power", "auxpower", "mdi:flash", POWER_WATT),
    WFSensorConfig("Loop Pump Power", "looppumppower", "mdi:flash", POWER_WATT),
    WFSensorConfig("Compressor Speed", "actualcompressorspeed", "mdi:speedometer"),
    WFSensorConfig("Fan Speed", "airflowcurrentspeed", "mdi:fan"),
]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Waterfurnace sensor."""
    if discovery_info is None:
        return

    sensors = []
    client = hass.data[WF_DOMAIN]
    for sconfig in SENSORS:
        sensors.append(WaterFurnaceSensor(client, sconfig))

    add_entities(sensors)


class WaterFurnaceSensor(SensorEntity):
    """Implementing the Waterfurnace sensor."""

    def __init__(self, client, config):
        """Initialize the sensor."""
        self.client = client
        self._name = config.friendly_name
        self._attr = config.field
        self._state = None
        self._icon = config.icon
        self._unit_of_measurement = config.unit_of_measurement
        self._attr_device_class = config.device_class

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(self.client.unit)}_{slugify(self._attr)}"
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return icon."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, UPDATE_TOPIC, self.async_update_callback
            )
        )

    @callback
    def async_update_callback(self):
        """Update state."""
        if self.client.data is not None:
            self._state = getattr(self.client.data, self._attr, None)
            self.async_write_ha_state()
