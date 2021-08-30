"""Support for IoTaWatt Energy monitor."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import COORDINATOR, DOMAIN, ENTITY_DESCRIPTION_KEY_MAP, SIGNAL_ADD_DEVICE
from .entity import IotaWattEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    entities = []

    # pylint: disable=unused-variable
    for idx, ent in enumerate(coordinator.data["sensors"]):
        entity = IotaWattSensor(
            coordinator=coordinator,
            key=ent,
            mac_address=coordinator.data["sensors"][ent].hub_mac_address,
            name=coordinator.data["sensors"][ent].getName(),
            entity_description=ENTITY_DESCRIPTION_KEY_MAP.get(
                coordinator.data["sensors"][ent].getUnit(),
                SensorEntityDescription("base_sensor"),
            ),
        )
        entities.append(entity)

    async_add_entities(entities)

    async def async_new_entities(sensor_info):
        """Add an entity."""
        ent = sensor_info["entity"]
        hub_mac_address = sensor_info["mac_address"]
        name = sensor_info["name"]
        unit = sensor_info["unit"]

        entity = IotaWattSensor(
            coordinator=coordinator,
            key=ent,
            mac_address=hub_mac_address,
            name=name,
            entity_description=ENTITY_DESCRIPTION_KEY_MAP.get(
                unit, SensorEntityDescription("base_sensor")
            ),
        )
        entities = [entity]
        async_add_entities(entities)

    async_dispatcher_connect(hass, SIGNAL_ADD_DEVICE, async_new_entities)


class IotaWattSensor(IotaWattEntity, SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    def __init__(self, coordinator, key, mac_address, name, entity_description):
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator, entity=key, mac_address=mac_address, name=name
        )

        sensor = self.coordinator.data["sensors"][key]
        self._ent = key
        self._io_type = sensor.getType()
        self._attr_force_update = True
        self._attr_name = f"IoTaWatt {sensor.getType()} {coordinator.data['sensors'][self._ent].getName()}"
        self._attr_unique_id = self.coordinator.data["sensors"][self._ent].getSensorID()
        self.entity_description = entity_description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._ent not in self.coordinator.data["sensors"]:
            entity_registry.async_get(self.hass).async_remove(self.entity_id)
            return

        super()._handle_coordinator_update()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        if self._io_type == "Input":
            channel = self.coordinator.data["sensors"][self._ent].getChannel()
            attrs = {"type": self._io_type, "channel": channel}
        else:
            attrs = {"type": self._io_type}

        return attrs

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data["sensors"][self._ent].getValue()
