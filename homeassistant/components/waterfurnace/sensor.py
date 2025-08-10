"""Support for Waterfurnace."""

from __future__ import annotations

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

from . import DOMAIN, UPDATE_TOPIC, WaterFurnaceData

SENSORS = [
    SensorEntityDescription(name="Furnace Mode", key="mode", icon="mdi:gauge"),
    SensorEntityDescription(
        name="Total Power",
        key="totalunitpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Active Setpoint",
        key="tstatactivesetpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        name="Leaving Air",
        key="leavingairtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        name="Room Temp",
        key="tstatroomtemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        name="Loop Temp",
        key="enteringwatertemp",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        name="Humidity Set Point",
        key="tstathumidsetpoint",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        name="Humidity",
        key="tstatrelativehumidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        name="Compressor Power",
        key="compressorpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Fan Power",
        key="fanpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Aux Power",
        key="auxpower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Loop Pump Power",
        key="looppumppower",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    SensorEntityDescription(
        name="Compressor Speed", key="actualcompressorspeed", icon="mdi:speedometer"
    ),
    SensorEntityDescription(
        name="Fan Speed", key="airflowcurrentspeed", icon="mdi:fan"
    ),
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

    client = hass.data[DOMAIN]

    add_entities(WaterFurnaceSensor(client, description) for description in SENSORS)


class WaterFurnaceSensor(SensorEntity):
    """Implementing the Waterfurnace sensor."""

    _attr_should_poll = False

    def __init__(
        self, client: WaterFurnaceData, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.client = client
        self.entity_description = description

        # This ensures that the sensors are isolated per waterfurnace unit
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"wf_{slugify(self.client.unit)}_{slugify(description.key)}"
        )

    async def async_added_to_hass(self) -> None:
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
            self._attr_native_value = getattr(
                self.client.data, self.entity_description.key, None
            )
            self.async_write_ha_state()
