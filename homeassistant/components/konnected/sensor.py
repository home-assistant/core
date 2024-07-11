"""Support for DHT and DS18B20 sensors attached to a Konnected device."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_NAME,
    CONF_SENSORS,
    CONF_TYPE,
    CONF_ZONE,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as KONNECTED_DOMAIN, SIGNAL_DS18B20_NEW

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "humidity": SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors attached to a Konnected device from a config entry."""
    data = hass.data[KONNECTED_DOMAIN]
    device_id = config_entry.data["id"]

    # Initialize all DHT sensors.
    dht_sensors = [
        sensor
        for sensor in data[CONF_DEVICES][device_id][CONF_SENSORS]
        if sensor[CONF_TYPE] == "dht"
    ]
    entities = [
        KonnectedSensor(device_id, data=sensor_config, description=description)
        for sensor_config in dht_sensors
        for description in SENSOR_TYPES.values()
    ]

    async_add_entities(entities)

    @callback
    def async_add_ds18b20(attrs):
        """Add new KonnectedSensor representing a ds18b20 sensor."""
        sensor_config = next(
            (
                s
                for s in data[CONF_DEVICES][device_id][CONF_SENSORS]
                if s[CONF_TYPE] == "ds18b20" and s[CONF_ZONE] == attrs.get(CONF_ZONE)
            ),
            None,
        )

        async_add_entities(
            [
                KonnectedSensor(
                    device_id,
                    sensor_config,
                    SENSOR_TYPES["temperature"],
                    addr=attrs.get("addr"),
                    initial_state=attrs.get("temp"),
                )
            ],
            True,
        )

    # DS18B20 sensors entities are initialized when they report for the first
    # time. Set up a listener for that signal from the Konnected component.
    async_dispatcher_connect(hass, SIGNAL_DS18B20_NEW, async_add_ds18b20)


class KonnectedSensor(SensorEntity):
    """Represents a Konnected DHT Sensor."""

    def __init__(
        self,
        device_id,
        data,
        description: SensorEntityDescription,
        addr=None,
        initial_state=None,
    ) -> None:
        """Initialize the entity for a single sensor_type."""
        self.entity_description = description
        self._addr = addr
        self._data = data
        self._zone_num = self._data.get(CONF_ZONE)
        self._attr_unique_id = addr or f"{device_id}-{self._zone_num}-{description.key}"

        # set initial state if known at initialization
        self._attr_native_value = initial_state
        if initial_state:
            self._attr_native_value = round(float(initial_state), 1)

        # set entity name if given
        if name := self._data.get(CONF_NAME):
            name += f" {description.name}"
        self._attr_name = name

        self._attr_device_info = DeviceInfo(identifiers={(KONNECTED_DOMAIN, device_id)})

    async def async_added_to_hass(self) -> None:
        """Store entity_id and register state change callback."""
        entity_id_key = self._addr or self.entity_description.key
        self._data[entity_id_key] = self.entity_id
        async_dispatcher_connect(
            self.hass, f"konnected.{self.entity_id}.update", self.async_set_state
        )

    @callback
    def async_set_state(self, state):
        """Update the sensor's state."""
        if self.entity_description.key == "humidity":
            self._attr_native_value = int(float(state))
        else:
            self._attr_native_value = round(float(state), 1)
        self.async_write_ha_state()
